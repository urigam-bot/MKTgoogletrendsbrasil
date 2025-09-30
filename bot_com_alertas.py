import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd
from pytrends.request import TrendReq
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import time
import os
import json
from threading import Thread
import schedule

# Configuração do logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações do bot
TELEGRAM_TOKEN = "8432782133:AAGz0nkNXk3G2zOxY9iSfoLiF_3w3KhFFBc"
CHAT_ID = 5272804713

# Palavras fixas para monitoramento
PALAVRAS_FIXAS = [
    "como fazer", "desenvolvimento", "treinamento", "curso online",
    "ebook", "negócio online", "vendas online", "marketing",
    "empreendedorismo", "renda extra"
]

# Configurações de alertas
LIMITE_ALERTA = 25.0  # Alerta quando subir +25%
ARQUIVO_HISTORICO = "historico_alertas.json"
ARQUIVO_DADOS = "dados_palavras.json"

class AlertSystem:
    def __init__(self, bot_token):
        self.bot = Bot(token=bot_token)
        self.alertas_ativos = True
        self.historico = self.carregar_historico()
        self.dados_anteriores = self.carregar_dados()
    
    def carregar_historico(self):
        """Carrega histórico de alertas"""
        try:
            if os.path.exists(ARQUIVO_HISTORICO):
                with open(ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except:
            return []
    
    def salvar_historico(self):
        """Salva histórico de alertas"""
        try:
            with open(ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f:
                json.dump(self.historico, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao salvar histórico: {e}")
    
    def carregar_dados(self):
        """Carrega dados anteriores das palavras"""
        try:
            if os.path.exists(ARQUIVO_DADOS):
                with open(ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}
    
    def salvar_dados(self, dados):
        """Salva dados atuais das palavras"""
        try:
            with open(ARQUIVO_DADOS, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao salvar dados: {e}")
    
    async def verificar_alertas(self):
        """Verifica se alguma palavra atingiu o limite de alerta"""
        if not self.alertas_ativos:
            return
        
        print("🔍 Verificando alertas...")
        analyzer = TrendsAnalyzer()
        
        try:
            # Gerar dados atuais
            resultados = analyzer.gerar_relatorio_completo()
            dados_atuais = {}
            
            for resultado in resultados:
                dados_atuais[resultado['palavra']] = {
                    'media_12m': resultado['media_12m'],
                    'media_7d': resultado['media_7d'],
                    'variacao': resultado['variacao'],
                    'timestamp': datetime.now().isoformat()
                }
            
            # Verificar alertas
            alertas_disparados = []
            
            for palavra, dados in dados_atuais.items():
                if dados['variacao'] >= LIMITE_ALERTA:
                    # Verificar se já foi alertado recentemente (últimas 24h)
                    ja_alertado = False
                    for alerta in self.historico:
                        if (alerta['palavra'] == palavra and 
                            datetime.fromisoformat(alerta['timestamp']) > datetime.now() - timedelta(hours=24)):
                            ja_alertado = True
                            break
                    
                    if not ja_alertado:
                        alertas_disparados.append({
                            'palavra': palavra,
                            'variacao': dados['variacao'],
                            'media_7d': dados['media_7d'],
                            'media_12m': dados['media_12m']
                        })
            
            # Enviar alertas
            if alertas_disparados:
                await self.enviar_alertas(alertas_disparados)
            
            # Salvar dados atuais
            self.salvar_dados(dados_atuais)
            self.dados_anteriores = dados_atuais
            
        except Exception as e:
            print(f"Erro na verificação de alertas: {e}")
    
    async def enviar_alertas(self, alertas):
        """Envia alertas para o Telegram"""
        try:
            mensagem = "🚨 **ALERTA DE TENDÊNCIA!**\n\n"
            
            for alerta in alertas:
                mensagem += f"📈 **{alerta['palavra'].title()}**\n"
                mensagem += f"🔥 Subiu **+{alerta['variacao']:.1f}%** em 7 dias!\n"
                mensagem += f"📊 Atual: {alerta['media_7d']} | Base: {alerta['media_12m']}\n\n"
                
                # Adicionar ao histórico
                self.historico.append({
                    'palavra': alerta['palavra'],
                    'variacao': alerta['variacao'],
                    'timestamp': datetime.now().isoformat(),
                    'tipo': 'alta'
                })
            
            mensagem += f"⏰ **Detectado em:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}\n"
            mensagem += f"🎯 **Limite configurado:** +{LIMITE_ALERTA}%"
            
            await self.bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode='Markdown')
            
            # Salvar histórico
            self.salvar_historico()
            
            print(f"✅ {len(alertas)} alerta(s) enviado(s)!")
            
        except Exception as e:
            print(f"Erro ao enviar alertas: {e}")

class TrendsAnalyzer:
    def __init__(self):
        self.pytrends = TrendReq(hl='pt-BR', tz=360)
    
    def analisar_palavra(self, palavra):
        """Analisa uma palavra específica"""
        try:
            print(f"🔍 Analisando: {palavra}")
            
            # Dados de 12 meses
            self.pytrends.build_payload([palavra], cat=0, timeframe='today 12-m', geo='BR', gprop='')
            dados_12m = self.pytrends.interest_over_time()
            time.sleep(2)
            
            # Dados de 7 dias
            self.pytrends.build_payload([palavra], cat=0, timeframe='now 7-d', geo='BR', gprop='')
            dados_7d = self.pytrends.interest_over_time()
            time.sleep(2)
            
            if dados_12m.empty or dados_7d.empty:
                return None
            
            # Cálculos
            media_12m = dados_12m[palavra].mean()
            media_7d = dados_7d[palavra].mean()
            
            # Determinar tendência
            if media_7d > media_12m * 1.1:
                status = "🔼 SUBINDO"
                variacao = ((media_7d - media_12m) / media_12m) * 100
            elif media_7d < media_12m * 0.9:
                status = "🔽 CAINDO"
                variacao = ((media_7d - media_12m) / media_12m) * 100
            else:
                status = "➡️ ESTÁVEL"
                variacao = 0
            
            return {
                'palavra': palavra,
                'media_12m': round(media_12m, 1),
                'media_7d': round(media_7d, 1),
                'status': status,
                'variacao': round(variacao, 1)
            }
            
        except Exception as e:
            print(f"❌ Erro ao analisar {palavra}: {e}")
            return None
    
    def gerar_relatorio_completo(self):
        """Gera relatório das 10 palavras fixas"""
        try:
            print("🔍 Gerando relatório completo...")
            resultados = []
            
            # Dividir em grupos para evitar rate limit
            grupos = [PALAVRAS_FIXAS[:5], PALAVRAS_FIXAS[5:]]
            
            for i, grupo in enumerate(grupos, 1):
                print(f"📊 Processando grupo {i}...")
                
                # 12 meses
                self.pytrends.build_payload(grupo, cat=0, timeframe='today 12-m', geo='BR', gprop='')
                dados_12m = self.pytrends.interest_over_time()
                time.sleep(3)
                
                # 7 dias
                self.pytrends.build_payload(grupo, cat=0, timeframe='now 7-d', geo='BR', gprop='')
                dados_7d = self.pytrends.interest_over_time()
                time.sleep(3)
                
                # Processar cada palavra do grupo
                for palavra in grupo:
                    if palavra in dados_12m.columns and palavra in dados_7d.columns:
                        media_12m = dados_12m[palavra].mean()
                        media_7d = dados_7d[palavra].mean()
                        
                        # Determinar tendência
                        if media_7d > media_12m * 1.1:
                            status = "🔼 SUBINDO"
                            variacao = ((media_7d - media_12m) / media_12m) * 100
                        elif media_7d < media_12m * 0.9:
                            status = "🔽 CAINDO"
                            variacao = ((media_7d - media_12m) / media_12m) * 100
                        else:
                            status = "➡️ ESTÁVEL"
                            variacao = 0
                        
                        resultados.append({
                            'palavra': palavra,
                            'media_12m': round(media_12m, 1),
                            'media_7d': round(media_7d, 1),
                            'status': status,
                            'variacao': round(variacao, 1)
                        })
            
            return resultados
            
        except Exception as e:
            print(f"❌ Erro no relatório completo: {e}")
            return []

# Instâncias globais
analyzer = TrendsAnalyzer()
alert_system = AlertSystem(TELEGRAM_TOKEN)

# Comandos do bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    mensagem = """
🤖 **Bot de Análise Google Trends Brasil**

📊 **Comandos disponíveis:**

🔹 `/relatorio` - Relatório das 10 palavras monitoradas
🔹 `/pesquisar [palavra]` - Análise individual de qualquer palavra
🔹 `/palavras` - Ver lista das palavras monitoradas
🔹 `/alertas` - Gerenciar sistema de alertas
🔹 `/historico` - Ver histórico de alertas
🔹 `/ajuda` - Lista de comandos

💡 **Exemplo de uso:**
`/pesquisar bicicleta`
`/pesquisar inteligência artificial`

🚨 **Sistema de Alertas:**
Notifica quando palavras sobem +25% em 7 dias!

🚀 **Pronto para analisar tendências!**
    """
    await update.message.reply_text(mensagem, parse_mode='Markdown')

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ajuda"""
    mensagem = """
📋 **GUIA DE COMANDOS**

🔸 **`/relatorio`**
   Gera relatório completo das 10 palavras fixas
   
🔸 **`/pesquisar [palavra]`**
   Analisa qualquer palavra específica
   
🔸 **`/palavras`**
   Mostra as 10 palavras monitoradas
   
🔸 **`/alertas`**
   Ativar/desativar sistema de alertas
   Configurar limite de alerta
   
🔸 **`/historico`**
   Ver últimos alertas disparados

📊 **Como funciona a análise:**
• Dados de 12 meses vs 7 dias
• +10% = 🔼 SUBINDO | -10% = 🔽 CAINDO
• Entre -10% e +10% = ➡️ ESTÁVEL

🚨 **Sistema de Alertas:**
• Verifica a cada 6 horas
• Alerta quando palavra sobe +25%
• Evita spam (1 alerta por palavra/24h)

🇧🇷 **Todos os dados são do Brasil**
    """
    await update.message.reply_text(mensagem, parse_mode='Markdown')

async def palavras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /palavras"""
    mensagem = "📋 **Palavras Monitoradas:**\n\n"
    for i, palavra in enumerate(PALAVRAS_FIXAS, 1):
        mensagem += f"{i:2d}. {palavra}\n"
    
    mensagem += f"\n📊 **Total:** {len(PALAVRAS_FIXAS)} palavras"
    mensagem += f"\n🚨 **Limite de alerta:** +{LIMITE_ALERTA}%"
    mensagem += "\n\n💡 Use `/relatorio` para análise completa"
    
    await update.message.reply_text(mensagem, parse_mode='Markdown')

async def pesquisar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /pesquisar [palavra]"""
    if not context.args:
        await update.message.reply_text(
            "❌ **Uso correto:** `/pesquisar [palavra]`\n\n"
            "📝 **Exemplos:**\n"
            "• `/pesquisar bicicleta`\n"
            "• `/pesquisar inteligência artificial`\n"
            "• `/pesquisar bitcoin`",
            parse_mode='Markdown'
        )
        return
    
    palavra = ' '.join(context.args).lower()
    msg_processando = await update.message.reply_text(f"🔍 **Analisando:** `{palavra}`\n⏳ Aguarde...")
    
    try:
        resultado = analyzer.analisar_palavra(palavra)
        
        if resultado:
            # Verificar se é um alerta
            emoji_alerta = ""
            if resultado['variacao'] >= LIMITE_ALERTA:
                emoji_alerta = " 🚨"
            
            mensagem = f"""
🔍 **Análise: {resultado['palavra'].title()}**{emoji_alerta}

📊 **Dados coletados:**
• 12 meses: {resultado['media_12m']}
• 7 dias: {resultado['media_7d']}

📈 **Status:** {resultado['status']}
"""
            if resultado['variacao'] != 0:
                mensagem += f"📊 **Variação:** {resultado['variacao']:+.1f}%"
                
                if resultado['variacao'] >= LIMITE_ALERTA:
                    mensagem += f"\n🚨 **ALERTA!** Acima do limite (+{LIMITE_ALERTA}%)"
            
            mensagem += f"\n\n🇧🇷 **Região:** Brasil"
            mensagem += f"\n⏰ **Gerado em:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
            
        else:
            mensagem = f"❌ **Erro ao analisar:** `{palavra}`\n\n"
            mensagem += "🔄 **Tente novamente em alguns minutos**"
        
        await msg_processando.edit_text(mensagem, parse_mode='Markdown')
        
    except Exception as e:
        await msg_processando.edit_text(
            f"❌ **Erro inesperado:** `{str(e)}`",
            parse_mode='Markdown'
        )

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /relatorio"""
    msg_processando = await update.message.reply_text(
        "📊 **Gerando relatório completo...**\n"
        "⏳ Isso pode levar 2-3 minutos"
    )
    
    try:
        resultados = analyzer.gerar_relatorio_completo()
        
        if resultados:
            # Contar tendências
            subindo = sum(1 for r in resultados if "SUBINDO" in r['status'])
            caindo = sum(1 for r in resultados if "CAINDO" in r['status'])
            estavel = sum(1 for r in resultados if "ESTÁVEL" in r['status'])
            
            # Verificar alertas
            alertas = sum(1 for r in resultados if r['variacao'] >= LIMITE_ALERTA)
            
            # Ordenar por média de 7 dias
            resultados.sort(key=lambda x: x['media_7d'], reverse=True)
            
            mensagem = f"""
🤖 **Relatório Google Trends Brasil**
📅 **Gerado em:** {datetime.now().strftime('%d/%m/%Y às %H:%M')}

📊 **Resumo das Tendências:**
🔼 Subindo: {subindo} | 🔽 Caindo: {caindo} | ➡️ Estável: {estavel}
"""
            
            if alertas > 0:
                mensagem += f"🚨 **Alertas:** {alertas} palavra(s) acima de +{LIMITE_ALERTA}%\n"
            
            mensagem += f"\n🏆 **Ranking (últimos 7 dias):**\n"
            
            for i, resultado in enumerate(resultados, 1):
                emoji_alerta = " 🚨" if resultado['variacao'] >= LIMITE_ALERTA else ""
                mensagem += f"{i:2d}. {resultado['palavra']}: {resultado['media_7d']} {resultado['status']}{emoji_alerta}\n"
            
            mensagem += f"\n🇧🇷 **Região:** Brasil"
            
        else:
            mensagem = "❌ **Erro ao gerar relatório**"
        
        await msg_processando.edit_text(mensagem, parse_mode='Markdown')
        
    except Exception as e:
        await msg_processando.edit_text(f"❌ **Erro:** `{str(e)}`", parse_mode='Markdown')

async def alertas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /alertas"""
    if context.args:
        comando = context.args[0].lower()
        
        if comando == "ativar":
            alert_system.alertas_ativos = True
            mensagem = "✅ **Alertas ATIVADOS!**\n\n🔍 Verificação a cada 6 horas"
        elif comando == "desativar":
            alert_system.alertas_ativos = False
            mensagem = "❌ **Alertas DESATIVADOS!**"
        elif comando == "teste":
            await alert_system.verificar_alertas()
            mensagem = "🧪 **Teste de alertas executado!**\nVerifique se recebeu notificações."
        else:
            mensagem = "❌ **Comando inválido!**\nUse: `/alertas ativar`, `/alertas desativar` ou `/alertas teste`"
    else:
        status = "✅ ATIVO" if alert_system.alertas_ativos else "❌ INATIVO"
        mensagem = f"""
🚨 **Sistema de Alertas**

📊 **Status:** {status}
🎯 **Limite:** +{LIMITE_ALERTA}% em 7 dias
⏰ **Frequência:** A cada 6 horas
📱 **Destino:** Este chat

🔧 **Comandos:**
• `/alertas ativar` - Ativar alertas
• `/alertas desativar` - Desativar alertas
• `/alertas teste` - Testar sistema

📋 **Como funciona:**
• Monitora as 10 palavras fixas
• Alerta quando variação ≥ +{LIMITE_ALERTA}%
• Evita spam (1 alerta/palavra/24h)
• Salva histórico automaticamente
        """
    
    await update.message.reply_text(mensagem, parse_mode='Markdown')

async def historico_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /historico"""
    historico = alert_system.historico
    
    if not historico:
        mensagem = "📋 **Histórico de Alertas**\n\n❌ Nenhum alerta disparado ainda."
    else:
        # Últimos 10 alertas
        ultimos = sorted(historico, key=lambda x: x['timestamp'], reverse=True)[:10]
        
        mensagem = "📋 **Últimos Alertas Disparados:**\n\n"
        
        for i, alerta in enumerate(ultimos, 1):
            data = datetime.fromisoformat(alerta['timestamp']).strftime('%d/%m às %H:%M')
            mensagem += f"{i:2d}. **{alerta['palavra'].title()}**\n"
            mensagem += f"    📈 +{alerta['variacao']:.1f}% | 📅 {data}\n\n"
        
        mensagem += f"📊 **Total de alertas:** {len(historico)}"
    
    await update.message.reply_text(mensagem, parse_mode='Markdown')

def executar_verificacao_alertas():
    """Executa verificação de alertas em thread separada"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(alert_system.verificar_alertas())
    loop.close()

def agendar_alertas():
    """Agenda verificações automáticas"""
    schedule.every(6).hours.do(executar_verificacao_alertas)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Verifica a cada minuto

def main():
    """Função principal"""
    print("🤖 Iniciando Bot com Sistema de Alertas...")
    
    # Iniciar thread de agendamento
    alert_thread = Thread(target=agendar_alertas, daemon=True)
    alert_thread.start()
    print("🚨 Sistema de alertas iniciado (verificação a cada 6h)")
    
    # Criar aplicação
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Adicionar handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ajuda", ajuda))
    application.add_handler(CommandHandler("help", ajuda))
    application.add_handler(CommandHandler("palavras", palavras))
    application.add_handler(CommandHandler("pesquisar", pesquisar))
    application.add_handler(CommandHandler("relatorio", relatorio))
    application.add_handler(CommandHandler("alertas", alertas_cmd))
    application.add_handler(CommandHandler("historico", historico_cmd))
    
    print("✅ Bot configurado!")
    print("🔄 Comandos disponíveis:")
    print("   /start, /relatorio, /pesquisar, /alertas, /historico")
    print("📱 Teste no Telegram!")
    
    # Rodar o bot
    application.run_polling()

if __name__ == '__main__':
    main()