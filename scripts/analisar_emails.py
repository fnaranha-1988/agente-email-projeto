from github import Github
import os

g = Github(os.environ["GITHUB_TOKEN"])

repo = g.get_repo("fnaranha-1988/agente-email-projeto")

issues = repo.get_issues(state="open")

print("\nPAINEL DE EMAILS\n")

for issue in issues:
    print("=================================")
    print("ASSUNTO:", issue.title)
    print("CRIADO EM:", issue.created_at)
    print("TEXTO:")
    print(issue.body[:1000])
    print("=================================\n")
