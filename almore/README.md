# Almore — mentores de negócios

Coletor diário de mentores brasileiros para a **Almore Inteligência Contábil**.

A Almore quer ser o escritório de contabilidade parceiro dos mentorados. Por isso o coletor busca mentores de **qualquer nicho de negócio, exceto contabilidade**: gente que acompanha donos de autopeças, e-commerce, restaurantes, clínicas, agências, franquias, transportadoras e os outros segmentos listados em `config/nichos.yml`. Mentor de contador, de escritório contábil ou site de contabilidade não entra.

O alvo é cerca de **50 mentores novos por dia**, de preferência com programa, comunidade ou turma de empresários e com base pequena ou média (até cerca de 100 mil seguidores no Instagram). Celebridades e perfis acima de 150 mil seguidores, quando o número é conhecido, ficam de fora. O que não aparece na fonte fica em branco. O coletor não completa ficha por achismo.

Tudo desta coleta mora em `almore/`, mais o workflow `.github/workflows/almore-mentores.yml`.

## Rodar na sua máquina

```bash
cd almore
python3 -m pip install -r requirements.txt
python3 -m almore_scraper
```

Atalhos úteis:

```bash
python3 -m almore_scraper --nichos restaurantes,ecommerce --max 10
python3 -m almore_scraper --sem-instagram
python3 -m unittest discover -s tests -v
```

A data de `data_entrada` e do arquivo do dia segue o fuso de São Paulo. Os arquivos gerados são:

- `data/mentores_YYYY-MM-DD.csv` — só os novos daquele dia
- `data/mentores_master.csv` — histórico, usado para não repetir gente
- `data/last_run.json` — o que a execução conseguiu e o que foi bloqueado

Os CSV usam UTF-8 com BOM, para abrir no Excel.

## Nichos

A lista fica em `config/nichos.yml`. Cada dia começa num ponto diferente da lista (a data gira o índice) e segue em frente até juntar candidatos suficientes ou estourar o teto de buscas. Dá para forçar segmentos com `--nichos id1,id2`.

Para incluir um segmento, copie um bloco em `nichos`. O `id` não pode conter `contab`. `consultas_extras` entra na frente dos templates; no máximo quatro consultas por nicho são usadas. `ignorar_handles` é a lista curta de celebridades que não são o público.

## Agendamento

O workflow roda todo dia às **10:45 UTC (07:45 em Brasília)** e também aceita execução manual (`workflow_dispatch`). Ele instala `almore/requirements.txt`, grava os CSV e faz commit em `almore/data/`.

No disparo manual dá para preencher `max` e `nichos`.

O repositório precisa permitir que o `GITHUB_TOKEN` faça push (permissão de escrita em Actions). Há um grupo de concorrência para não rodar duas coletas da Almore ao mesmo tempo.

## Instagram

A ficha tenta, nesta ordem:

1. página pública do mentor (link, JSON-LD, texto);
2. snippet do DuckDuckGo para um handle **que já apareceu** na página do mentor ou num resultado que já era o perfil, de onde muitas vezes saem seguidores e um trecho da bio;
3. [Instaloader](https://instaloader.github.io/), se houver sessão.

O coletor não escolhe um Instagram só porque o nome é parecido. Handle de homônimo fica em branco.

Sem sessão, o Instaloader anônimo hoje cai na tela de login a partir de IP de datacenter (GitHub Actions incluso) e o coletor **para de insistir** depois de poucas falhas. Seguidores e bio que já vieram da busca permanecem. `ultimos_posts` só entra com post de fato: o Instaloader, quando a sessão funciona, ou uma URL de post que a busca mostre com data recente (até 18 meses). Post antigo indexado não é tratado como “último”.

Para usar uma conta secundária (não a conta principal da Almore):

```bash
python3 -m pip install instaloader
python3 -m instaloader --login=USUARIO_SECUNDARIO
```

O arquivo de sessão no Linux fica em `~/.config/instaloader/session-USUARIO_SECUNDARIO`. Gere o segredo em base64:

```bash
base64 -w0 ~/.config/instaloader/session-USUARIO_SECUNDARIO
```

No macOS: `base64 < ~/.config/instaloader/session-USUARIO_SECUNDARIO | tr -d '\n'`.

Secrets do repositório:

| Secret | Conteúdo |
| --- | --- |
| `IG_USERNAME` | usuário da conta secundária |
| `IG_SESSIONFILE` | conteúdo do arquivo de sessão, em base64 |

Não coloque a senha no GitHub. Se os secrets não existirem, a coleta segue sem sessão. A sessão é um pickle do Instaloader; trate o secret como credencial.

## Colunas

| Coluna | Conteúdo |
| --- | --- |
| `nome` | pessoa ou marca, como apareceu na fonte |
| `nicho` | segmento da configuração que levou até o mentor |
| `instagram_handle` / `instagram_url` | perfil, quando houve confirmação |
| `linkedin_url` | perfil `/in/` ou, na falta dele, página `/company/` |
| `site` | site do mentor, não a matéria de jornal nem a página da Hotmart |
| `programa_mentoria` | nome do programa, método ou comunidade, se deu para ler |
| `cidade_uf` | só com pista explícita (`Cidade/UF` ou “em Campinas”) |
| `seguidores` | número inteiro, sem ponto. Vazio se não houve fonte |
| `menciona_contador_parceiro` | `yes \| trecho` quando o texto cita parceiro; `no` quando o texto lido não cita; vazio quando quase não havia texto |
| `ultimos_posts` | até 3 URLs, com trecho da legenda quando existe, separadas por ` ;; ` |
| `fonte_url` | página em que a pessoa foi encontrada |
| `data_entrada` | dia em São Paulo |

Quem já está no master não volta no CSV do dia. A mesma pessoa encontrada de novo no mesmo dia também não duplica.

## O que a busca realmente faz

O provedor principal é o HTML do DuckDuckGo (`html.duckduckgo.com`), via biblioteca padrão do Python. Consultas `site:` disparam o desafio de bot do DuckDuckGo, então elas não são usadas. A biblioteca `requests` recebe HTTP 202 com esse desafio; o `urllib` recebe a página de resultados. O Bing só entra se o DuckDuckGo não devolver nada, e a página é descartada quando os resultados não têm relação com a consulta (isso aconteceu com frequência).

Não há chave paga. O limite de buscas, as pausas e a desistência do Instagram estão no YAML para ajustar sem mexer no código.

## Limites

- Cinquenta linhas não são garantidas. Se a busca desafiar ou o nicho do dia render pouco, o arquivo vem mais curto em vez de ser completado com nome inventado.
- Seguidores vindos de snippet podem estar um pouco defasados em relação ao perfil.
- Sem sessão do Instagram, `ultimos_posts` tende a ficar vazio.
- Perfil com seguidores desconhecidos pode passar; o corte de 150 mil só vale quando o número foi lido.
- Há risco de homônimo. Se o handle não veio do site do mentor, o coletor só grava um Instagram quando o nome confere e a bio/título conversa com o nicho, ou quando o handle é muito parecido com o nome.
- A menção a contador parceiro é uma leitura do texto coletado, não uma auditoria do escritório.
- Os dados são públicos e profissionais. O uso para contato B2B da Almore precisa respeitar a LGPD e os termos das plataformas. Não use a coleta para mandar spam nem para criar conta falsa em massa.

## Testes

```bash
cd almore
python3 -m unittest discover -s tests -v
```
