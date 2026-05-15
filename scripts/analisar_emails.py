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

def extrair_conversation_id(texto):
    match = re.search(r"ID Conversa:\s*(.*)", texto or "")
    return match.group(1).strip() if match else None

def fechar_duplicatas(issues_lista):
    grupos = defaultdict(list)

    for issue in issues_lista:
        conv_id = extrair_conversation_id(issue.body)
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
                dup.edit(state="closed", state_reason="not_planned")
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
Você é um agente de gestão de e-mails de Engenharia, Projetos, CapEx e Implantação.

Seu objetivo é analisar e consolidar informações relevantes dos e-mails.

Sempre analise o texto a partir do corpo do e-mail para ver como está o tema.

Você vai agrupar os temas verificando o que está escrito após Assunto: e Corpo do e-mail:

O objetivo é retornar o status do tema e qual ação tenho que ter sobre

Analise os e-mails abaixo, agrupe por projeto ou assunto e retorne SOMENTE JSON válido.

Cada item do JSON deve conter:

- projeto_assunto
- status
- pendencia
- responsavel
- prazo
- ultima_atualizacao
- proximo_passo
- risco
- entrega_projeto
- grd_aprovado

Status permitidos:
- Pendente comigo
- Aguardando terceiro
- Em andamento
- Travado
- Concluído
- Informativo

Regras obrigatórias:

- Não invente informações.
- Utilize apenas os dados encontrados nos e-mails.
- Se não identificar uma informação, escrever "não identificado".
- Se não houver ação necessária, escrever "sem ação necessária".
- Considere sempre o e-mail mais recente do assunto/projeto.
- Ignore e-mails automáticos, newsletters, Teams, notificações e mensagens sem relevância de gestão.
- Priorize:
  - entregas de projeto;
  - aprovações;
  - pendências;
  - prazos;
  - riscos;
  - cobranças;
  - decisões técnicas;
  - GRD;
  - envio de documentos;
  - protocolos;
  - retorno de revisão.

Regras específicas:

- Se houver envio de projeto, memorial, relatório, prancha, orçamento, cronograma, documentação técnica ou entrega formal, preencher:
  entrega_projeto = "sim"

- Caso contrário:
  entrega_projeto = "não"

- Se houver indicação clara de aprovação de GRD, liberação de GRD, aceite de GRD ou validação de GRD:
  grd_aprovado = "sim"

- Se houver reprovação, pendência ou necessidade de ajuste:
  grd_aprovado = "não"

- Se não houver menção:
  grd_aprovado = "não identificado"

- Se Felipe foi cobrado e não respondeu:
  status = "Pendente comigo"

- Se Felipe cobrou terceiros e não houve retorno:
  status = "Aguardando terceiro"

- Se existir indefinição técnica, contratual ou gerencial:
  status = "Travado"

- Se houver somente comunicação sem ação:
  status = "Informativo"

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
    "risco",
    "entrega_projeto",
    "grd_aprovado"
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
