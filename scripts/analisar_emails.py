from github import Github
from openai import OpenAI
import os
import json
import pandas as pd
from datetime import datetime

g = Github(os.environ["GITHUB_TOKEN"])
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

repo = g.get_repo("fnaranha-1988/agente-email-projeto")

PALAVRAS_LIXO = [
    "teams", "microsoft", "github", "newsletter", "notificação",
    "notification", "noreply", "no-reply", "não responda",
    "naoresponda", "automático", "automatico", "assinatura",
    "convite", "cancelado", "lembrete", "reminder"
]

def eh_lixo(titulo, corpo):
    texto = f"{titulo} {corpo}".lower()
    return any(p in texto for p in PALAVRAS_LIXO)

issues = repo.get_issues(state="open")
emails = []

for issue in issues:
    if "painel" in [label.name.lower() for label in issue.labels]:
        continue

    titulo = issue.title or ""
    corpo = issue.body or ""

    if eh_lixo(titulo, corpo):
        continue

    emails.append({
        "titulo": titulo,
        "data": str(issue.created_at),
        "ultima_atualizacao": str(issue.updated_at),
        "corpo": corpo[:3000]
    })

prompt = f"""
Você é um agente de gestão de e-mails de Engenharia, Projetos e CapEx.

Analise os e-mails abaixo, agrupe por projeto ou assunto e retorne SOMENTE JSON válido.

Cada item do JSON deve ter estes campos:
- projeto_assunto
- status
- pendencia
- responsavel
- prazo
- ultima_atualizacao
- proximo_passo
- risco

Status permitidos:
- Pendente comigo
- Aguardando terceiro
- Em andamento
- Travado
- Concluído
- Informativo

Regras:
- Não invente informações.
- Se não identificar, escreva "não identificado".
- Se não houver ação, escreva "sem ação necessária".
- A data de última atualização deve considerar o e-mail mais recente daquele projeto/assunto.
- Ignore e-mails automáticos, newsletters, notificações e assuntos sem relevância de gestão.
- Priorize pendências, prazos, decisões e cobranças.

E-mails:
{emails}
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0,
    messages=[
        {
            "role": "system",
            "content": "Você retorna somente JSON válido. Não inventa informações."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
)

conteudo = response.choices[0].message.content.strip()

if conteudo.startswith("```json"):
    conteudo = conteudo.replace("```json", "").replace("```", "").strip()
elif conteudo.startswith("```"):
    conteudo = conteudo.replace("```", "").strip()

dados = json.loads(conteudo)

df = pd.DataFrame(dados)

colunas = [
    "projeto_assunto",
    "status",
    "pendencia",
    "responsavel",
    "prazo",
    "ultima_atualizacao",
    "proximo_passo",
    "risco"
]

for coluna in colunas:
    if coluna not in df.columns:
        df[coluna] = "não identificado"

df = df[colunas]

nome_arquivo = "painel_email_projetos.xlsx"
df.to_excel(nome_arquivo, index=False)

resumo_markdown = df.to_markdown(index=False)

repo.create_issue(
    title=f"Painel consolidado de e-mails - {datetime.now().strftime('%d/%m/%Y')}",
    body=resumo_markdown,
    labels=["painel"]
)

print("Painel gerado com sucesso.")
print(resumo_markdown)
