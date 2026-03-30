<div align="center">

# dw-cli-changer

**Gerencie perfis de `dw.json` e aplique em segundos.**

CLI em Python para salvar ambientes (hostname, credenciais, versão, cartridges) e gravar o `dw.json` certo em cada projeto — com fluxo interativo ou comandos diretos no terminal.

[![Python](https://img.shields.io/badge/python-3.10+-0A66C2?style=flat&logo=python&logoColor=white)](https://www.python.org/)

</div>

---

## Por que usar?

Quem trabalha com **Salesforce Commerce Cloud** (Demandware) costuma alternar entre sandboxes, lojas e versões de código. Trocar `dw.json` na mão é repetitivo e propenso a erro. Este projeto centraliza **perfis nomeados** em um único arquivo local e aplica o escolhido no **`dw.json` da pasta atual** com um comando.

---

## Funcionalidades

| Recurso | Descrição |
|--------|------------|
| **Perfis persistentes** | Armazena vários ambientes com nome, host, usuário, senha, `version` e opcionalmente `cartridgesPath`. |
| **Menu interativo** | Ao rodar sem subcomando, abre um menu guiado (com [Questionary](https://github.com/tmbo/questionary) quando o terminal suporta). |
| **CLI completa** | `create`, `edit`, `delete`, `list`, `select` — uso em scripts e CI quando fizer sentido. |
| **Saída JSON** | `list --json` para inspecionar o store programaticamente. |
| **Diretório configurável** | Variável `DW_CLI_CHANGER_HOME` para mudar onde os dados ficam salvos. |

---

## Requisitos

- **Python 3.10+**
- Dependência: `questionary` (prompts interativos)

---

## Instalação

Clone o repositório e instale em modo editável (recomendado para desenvolvimento):

```bash
git clone https://github.com/lbss9/dw-cli-changer.git
cd dw-cli-changer
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

O executável fica disponível como **`dw-cli-changer`**.

---

## Uso rápido

### Menu interativo (padrão)

```bash
cd /caminho/do/seu/projeto-sfcc
dw-cli-changer
```

### Comandos principais

```bash
# Listar perfis salvos
dw-cli-changer list

# Store completo em JSON
dw-cli-changer list --json

# Criar perfil (campos faltantes viram prompts)
dw-cli-changer create minha-loja \
  --hostname dev01-eu.mycompany.demandware.net \
  --username seu.usuario \
  --password 'sua-senha' \
  --version 22.7

# Editar perfil existente
dw-cli-changer edit minha-loja --version 22.8

# Aplicar perfil no dw.json do diretório atual (cria ou sobrescreve o arquivo)
dw-cli-changer select minha-loja

# Remover perfil
dw-cli-changer delete minha-loja
```

### Campos do perfil

Os dados gravados no `dw.json` seguem a forma normalizada esperada pela ferramenta:

- `hostname`, `username`, `password`, `version` — **obrigatórios**
- `cartridgesPath` — **opcional**

Na criação/edição, `code-version` também é aceito e mapeado para `version`.

---

## Onde os dados ficam salvos?

Por padrão:

```text
~/.dw-cli-changer/profiles.json
```

Para usar outro diretório:

```bash
export DW_CLI_CHANGER_HOME="$HOME/minha-pasta-dw"
```

---

## Segurança

As **senhas ficam em texto plano** no `profiles.json` local. Trate esse arquivo como credencial: permissões restritas no disco, não commitar no Git e não compartilhar a pasta de configuração.

