from github import Github
from openai import OpenAI
import os
import json
import pandas as pd
from datetime import datetime
from collections import defaultdict
import re

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

def extrair_conversation_id(titulo):
    match = re.search(r"\[CONV-(.*?)\]", titulo)
    return match.group(1) if match else None

def fechar_duplicatas(issues_lista):
    grupos = defaultdict(list)

    for issue in issues_lista:
        conv_id = extrair_conversation_id(issue.title)
        if conv_id:
            grupos[conv_id].append(issue)

    for conv_id, lista in grupos.items():
        if len(lista) <= 1:
            continue

        lista_ordenada = sorted(lista, key=lambda x: x.updated_at, reverse=True)
        manter = lista_ordenada[0]
        duplicadas = lista_ordenada[1:]

        for dup in duplicadas:
            try:
                dup.create_comment(
                    f"Fechada automaticamente como duplicata da Issue #{manter.number}."
                )
                dup.edit(
                    state="closed",
                    state_reason="not_planned"
                )
            except Exception as e:
                print(f"Erro ao fechar duplicata #{dup.number}: {e}")

issues_lista = list(repo.get_issues(state="open"))

fechar_duplicatas(issues_lista)

issues = repo.get_issues(state="open")
emails = []

for issue in issues:
    labels = [label.name.lower() for label in issue.labels]

    if "painel" in labels:
        continue

    titulo = issue.title or ""
    corpo = issue.body or ""

    if eh_lixo(titulo, corpo):
        continue

    emails.append({
        "numero_issue": issue.number,
        "titulo": titulo,
        "data_criacao": str(issue.created_at),
        "ultima_atualizacao": str(issue.updated_at),
        "corpo": corpo[:3000]
    })

if not emails:
    print("Nenhum e-mail relevante encontrado para análise.")
    exit()

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

Regras obrigatórias:
- Não invente informações.
- Use apenas os dados dos e-mails.
- Se não identificar, escreva "não identificado".
- Se não houver ação, escreva "sem ação necessária".
- A data de última atualização deve considerar o e-mail mais recente daquele projeto/assunto.
- Ignore e-mails automáticos, newsletters, notificações e assuntos sem relevância de gestão.
- Priorize pendências, prazos, decisões, cobranças e riscos.
- Se houver pergunta direcionada ao Felipe sem resposta posterior dele, classifique como "Pendente comigo".
- Se Felipe cobrou alguém e não houver resposta posterior, classifique como "Aguardando terceiro".
- Se houver decisão técnica, contratual ou gerencial sem definição, classifique como "Travado".

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
    title=f"Painel consolidado de e-mails - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    body=resumo_markdown,
    labels=["painel"]
)

print("Painel gerado com sucesso.")
print(resumo_markdown)
print(resumo_markdown)
