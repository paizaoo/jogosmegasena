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
# DIRETORIO_PLANILHA = r"C:\Users\vitor.souza\Documents\PASTA-MEGA-SENA\PLANILHA"

DIRETORIO_PLANILHA = os.path.join(os.getcwd(), "PLANILHA")
URL_CAIXA = "https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx"

if not os.path.exists(DIRETORIO_PLANILHA):
    os.makedirs(DIRETORIO_PLANILHA)

# --- FUNÇÃO DE CAPTURA (HEADLESS) ---
def baixar_planilha_caixa():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    prefs = {"download.default_directory": DIRETORIO_PLANILHA, "download.prompt_for_download": False}
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": DIRETORIO_PLANILHA})

    try:
        driver.get(URL_CAIXA)
        wait = WebDriverWait(driver, 30)
        botao = wait.until(EC.presence_of_element_located((By.ID, "btnResultados")))
        driver.execute_script("arguments[0].click();", botao)
        time.sleep(15) 
    finally:
        driver.quit()

# --- LÓGICA DE PROCESSAMENTO ---
def processar_dados():
    arquivos = [f for f in os.listdir(DIRETORIO_PLANILHA) if f.endswith('.xlsx')]
    if not arquivos:
        baixar_planilha_caixa()
        arquivos = [f for f in os.listdir(DIRETORIO_PLANILHA) if f.endswith('.xlsx')]

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
    # Carrega a página inicial (o HTML que te enviei antes)
    return render_template('index.html')

@app.route('/gerar')
def gerar_palpite():
    # RN01 e RN02: Recebe a quantidade escolhida no ComboBox
    qtd = int(request.args.get('qtd', 6))
    
    historico, todas_dezenas = processar_dados()
    
    # Estatística básica (Top 15 mais frequentes)
    frequencia = Counter(todas_dezenas)
    df_freq = pd.DataFrame(frequencia.items(), columns=['Dezena', 'Freq']).sort_values(by='Freq', ascending=False)
    
    mais_freq = list(df_freq.head(15)['Dezena'])
    menos_freq = list(df_freq.tail(15)['Dezena'])
    pool_misto = list(range(1, 61))

    # RN03: Lógica do Robô para gerar o jogo inédito
    random.seed(time.time()) # Seed dinâmica para o site não repetir o jogo para usuários diferentes
    
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

        # Verifica ineditismo (combinação de 6 números)
        comb_6 = list(combinations(jogo, 6))
        is_repetido = any(tuple(sorted(c)) in historico for c in comb_6)
        
        if not is_repetido:
            return jsonify({"jogo": jogo})
        
        tentativas += 1

    return jsonify({"erro": "Não foi possível gerar um jogo inédito. Tente novamente."})

if __name__ == "__main__":
    app.run(debug=True)