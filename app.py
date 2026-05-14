import os
import time
import pandas as pd
import random
from collections import Counter
from itertools import combinations
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

# --- CONFIGURAÇÕES DE CAMINHO ---
# Define o diretório baseado na localização do arquivo app.py (funciona no Git e Local)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_PLANILHA = os.path.join(BASE_DIR, "PLANILHA")
URL_CAIXA = "https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx"

if not os.path.exists(DIRETORIO_PLANILHA):
    os.makedirs(DIRETORIO_PLANILHA)

# --- FUNÇÃO DE CAPTURA (HEADLESS) ---
def baixar_planilha_caixa():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    # Se estiver rodando no Render, precisamos apontar para o binário do Chrome instalado pelo build script
    if os.path.exists("/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"):
        chrome_options.binary_location = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
    
    prefs = {
        "download.default_directory": DIRETORIO_PLANILHA, 
        "download.prompt_for_download": False,
        "directory_upgrade": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": DIRETORIO_PLANILHA})

    try:
        print("🔗 Acessando site da Caixa...")
        driver.get(URL_CAIXA)
        wait = WebDriverWait(driver, 30)
        botao = wait.until(EC.presence_of_element_located((By.ID, "btnResultados")))
        driver.execute_script("arguments[0].click();", botao)
        print("⏳ Aguardando download...")
        time.sleep(15) 
    finally:
        driver.quit()

# --- LÓGICA DE PROCESSAMENTO ---
def processar_dados():
    arquivos = [f for f in os.listdir(DIRETORIO_PLANILHA) if f.endswith('.xlsx')]
    
    # Se não houver arquivos, tenta baixar (Plano B)
    if not arquivos:
        print("⚠️ Planilha não encontrada. Iniciando download automático...")
        baixar_planilha_caixa()
        arquivos = [f for f in os.listdir(DIRETORIO_PLANILHA) if f.endswith('.xlsx')]

    if not arquivos:
        return None, None

    # Pega o arquivo mais recente na pasta
    arquivos.sort(key=lambda x: os.path.getmtime(os.path.join(DIRETORIO_PLANILHA, x)), reverse=True)
    caminho_excel = os.path.join(DIRETORIO_PLANILHA, arquivos[0])
    
    df = pd.read_excel(caminho_excel)
    dezenas_df = df.iloc[:, 2:8].dropna()
    
    historico = set()
    todas_dezenas = []
    for _, linha in dezenas_df.iterrows():
        jogo = sorted([int(n) for n in linha.values])
        historico.add(tuple(jogo))
        todas_dezenas.extend(jogo)
    
    return historico, todas_dezenas

# --- ROTAS DO SITE ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gerar')
def gerar_palpite():
    qtd = int(request.args.get('qtd', 6))
    
    historico, todas_dezenas = processar_dados()
    
    if historico is None:
        return jsonify({"erro": "Erro ao processar dados da Mega-Sena."})
    
    frequencia = Counter(todas_dezenas)
    df_freq = pd.DataFrame(frequencia.items(), columns=['Dezena', 'Freq']).sort_values(by='Freq', ascending=False)
    
    mais_freq = list(df_freq.head(15)['Dezena'])
    menos_freq = list(df_freq.tail(15)['Dezena'])
    pool_misto = list(range(1, 61))

    # RN03: Lógica do Robô para gerar o jogo inédito
    random.seed(time.time())
    
    tentativas = 0
    while tentativas < 1000:
        if qtd == 10:
            jogo = sorted(random.sample(mais_freq, 6) + random.sample(menos_freq, 4))
        elif qtd == 9:
            jogo = sorted(random.sample(mais_freq, 5) + random.sample(pool_misto, 4))
        elif qtd == 8:
            jogo = sorted(random.sample(mais_freq, 4) + random.sample(pool_misto, 4))
        elif qtd == 7:
            jogo = sorted(random.sample(mais_freq, 3) + random.sample(pool_misto, 4))
        else:
            jogo = sorted(random.sample(pool_misto, 6))

        # Verifica se o jogo (ou qualquer combinação de 6 dentro dele) já existiu
        comb_6 = list(combinations(jogo, 6))
        is_repetido = any(tuple(sorted(c)) in historico for c in comb_6)
        
        if not is_repetido:
            return jsonify({"jogo": jogo})
        
        tentativas += 1

    return jsonify({"erro": "Limite de tentativas atingido. Tente novamente."})

if __name__ == "__main__":
    # Configuração para rodar tanto local quanto no Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
