# Busca diária de mentores contábeis

Lista pública de prospecção da **Devant Labs** (IA para escritórios de contabilidade). O repositório está público: o recomendado é torná-lo **privado**, porque `data/` é uma lista de pessoas para abordar.

Todo dia o fluxo procura cerca de 20 mentores **novos** no Brasil: gente que vende mentoria, curso ou comunidade para contadores e donos de escritório contábil, de preferência com até 50 mil seguidores no Instagram. Não entra de novo quem já está em `data/mentores_master.csv`. Não entra, mesmo fora do cadastro, Anderson Hernandes, Fellipe Guerra, Lucas Lima (Contador Revoltado), Anderson Souza e Elcio Guioto.

Nada é inventado. Campo que a busca não confirmou fica vazio.

## O que sai em cada linha

| Campo | Conteúdo |
| --- | --- |
| `nome` | Nome da pessoa ou, se a oferta pública for de um instituto/comunidade, o nome dessa marca |
| `instagram_handle` | Com `@` |
| `instagram_url` | `https://www.instagram.com/<handle>/` |
| `linkedin_url` | Só se a URL `/in/` apareceu na busca ou na página |
| `site` | Página da oferta (site próprio ou produto na Hotmart) |
| `tema` | Frase pública da bio, do snippet ou da meta description. No máximo ~220 caracteres |
| `cidade_uf` | Só no formato `Cidade/UF` quando o texto traz a sigla |
| `seguidores` | Inteiro. Prefixo `~` quando a fonte publicou arredondado (`17K`, `6,5 mil`) |
| `menciona_ia` | `sim: trecho`, `não: …` somente se lemos bio ou página e não havia menção, ou vazio se não deu para julgar |
| `ultimos_posts` | Até 3 URLs. Legenda curta depois de `—`, posts separados por ` \|\| ` |
| `fonte_url` | Onde a pessoa foi encontrada |
| `data_entrada` | Data em `America/Sao_Paulo` |

O cadastro mestre usa essas mesmas colunas. As 20 pessoas do funil inicial estão em `data/seed/funil_mentores.csv` (arquivo original, com etapa e observações) e foram copiadas para `data/mentores_master.csv` sem essas colunas de CRM.

## Como a busca escolhe

1. Consultas em português, sem operador `site:`, na primeira página do DuckDuckGo HTML (`kl=br-pt`) e do Yahoo Brasil.
2. Entra perfil do Instagram, perfil do LinkedIn ou página de oferta (incluindo produto na Hotmart) cujo texto mostra mentoria/curso/comunidade **e** o público contador ou escritório contábil. "Mentora de contadores" conta. "Mentora de empresárias" não: o público não é o contador.
3. Sai artigo, blog, fórum, notícia, YouTube, anúncio e página em espanhol ou de outro país.
4. Sai quem já tem mais de 50.000 seguidores quando o número aparece. Quem não tem número fica no fim da fila: tamanho desconhecido não vira zero e não vira chute.
5. Deduplica por `@`, slug do LinkedIn e nome. O mesmo programa citado no Instagram e no site vira uma linha só.
6. Lê até 10 páginas de oferta para preencher LinkedIn, cidade e menção a IA.
7. Tenta o Instaloader nos handles finais. Anônimo por padrão. Se existir sessão (segredo abaixo), usa a conta secundária. No primeiro HTTP 429 ou pedido de login, **para**. O CSV continua com o que a busca já tinha.
8. Grava `data/mentores_YYYY-MM-DD.csv` (só os novos do dia) e acrescenta essas linhas ao mestre. `data/ultimo_run.json` guarda contagens, erros e exemplos de descarte.

Posts do Instaloader são os mais recentes do perfil. Se o Instagram bloqueou, os posts são os que o buscador indexou (com data do snippet, quando ela existe). Não são, nesse caso, uma leitura ao vivo do perfil.

## O que foi testado deste tipo de IP

Medido em rede de datacenter, a mesma classe de IP do GitHub Actions:

| Fonte | Resultado |
| --- | --- |
| DuckDuckGo HTML | Funciona. Traz perfil, seguidores e um trecho da bio. A página 2 repetiu a página 1, então cada consulta usa só a primeira. |
| Yahoo Brasil | Funciona e acha gente que o DuckDuckGo não trouxe na mesma consulta. |
| Bing HTML | HTTP 200, mas devolveu portal de notícia sem relação com a consulta. Não é usado. |
| `site:` no DuckDuckGo | HTTP 202, página de anomalia. As consultas não usam `site:`. |
| Instagram (perfil e embed) | Redireciona para login ou vem sem bio/seguidores. |
| Instaloader anônimo | HTTP 429 já na primeira ficha. O código não espera a retentativa de 30 minutos; interrompe e segue. |
| Alguns sites (ex.: helodecastro.com.br) | HTTP 403. A linha fica só com o que o buscador mostrou. |

A rodada gravada neste repositório está em `data/ultimo_run.json` e em `data/mentores_2026-11-09.csv`. O relógio de Brasília nessa execução era 21:56 de 9 de novembro de 2026 (já era 10 de novembro em UTC). O cron das 10:30 UTC cai no mesmo dia civil em Brasília.

## Rodar na sua máquina

Requer Python 3.11 ou 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scraper --max 20
```

A raiz do repositório precisa ser o diretório atual, porque a saída vai para `data/`. Testes, sem rede:

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

## Sessão opcional do Instagram

Sem segredo, a Action roda o Instaloader anônimo e, se levar 429, ignora o enriquecimento. Uma conta **secundária** (não a sua conta pessoal) aumenta a chance de ler bio, seguidores exatos e os 3 posts mais recentes.

Na sua máquina, uma vez:

```bash
instaloader --login=CONTA_SECUNDARIA
base64 -w 0 ~/.config/instaloader/session-CONTA_SECUNDARIA
```

No GitHub, em Settings → Secrets and variables → Actions:

| Segredo | Valor |
| --- | --- |
| `IG_USERNAME` | `CONTA_SECUNDARIA` |
| `IG_SESSIONFILE` | o base64 do arquivo de sessão, numa linha só |

O arquivo de sessão equivale a senha. Não commite, não cole no README, não use a conta principal. O workflow decodifica o segredo para `~/.config/instaloader/` do runner e apaga o runner no fim do job. Se o segredo estiver ausente ou inválido, a busca segue anônima.

Para testar a sessão localmente:

```bash
export IG_USERNAME=CONTA_SECUNDARIA
export IG_SESSIONFILE=$HOME/.config/instaloader/session-CONTA_SECUNDARIA
python -m scraper --max 20
```

## GitHub Actions

`.github/workflows/mentores-diarios.yml` dispara todo dia às **10:30 UTC (07:30 em Brasília)** e também em *Run workflow*. O `GITHUB_TOKEN` precisa poder dar push na branch padrão (`contents: write` já está no workflow). Se a branch `main` exigir pull request, ou o push do bot vai falhar: libere o `github-actions[bot]` nessa branch, ou o CSV do dia não entra no git.

O commit só mexe em `data/mentores_*.csv`, `data/mentores_master.csv` e `data/ultimo_run.json`. Não dispara de novo o agendamento, porque o workflow não escuta `push`.

`.github/workflows/testes.yml` roda o pytest em push e pull request. Não chama DuckDuckGo, Yahoo nem Instagram.

## Limites

- Vinte linhas é o teto, não uma cota. Se o dia render menos gente que passe no filtro, o CSV vem mais curto.
- Seguidores com `~` são o número publicado pelo buscador (`18K` vira `~18000`), não uma contagem ao vivo.
- LinkedIn sem login não é raspado. A URL entra só quando está no resultado ou no HTML da página.
- Mentoria muito nova, sem página indexada, não aparece.
- Conta grande sem o número de seguidores visível no snippet pode passar. Ela fica atrás de quem tem contagem conhecida e baixa.
- O texto de `menciona_ia` com `não` significa "não achei nas fontes que li", não uma varredura de todas as redes.
- Espelhos de Instagram (`imginn.com`, `picuki.com` e semelhantes) são ignorados. Não são o perfil nem o site da pessoa.

## O que esta máquina conseguiu gravar

A última execução que ainda recebeu resposta dos buscadores gravou três mentores novos, todos com sinal público de oferta para contadores e bem abaixo de 50 mil seguidores:

| Nome | Instagram | Seguidores | Posts no CSV |
| --- | --- | --- | --- |
| Aldo Dias | `@contadoraldodiasmentor` | 1075 | 2 URLs indexadas pelo buscador |
| Silvio | `@contador.protagonista` | 1526 | 3 URLs indexadas. O sobrenome não apareceu; o campo ficou só com o nome publicado |
| Fernando Coelho | `@fernandocoelhooficial` | ~18000 | 3 URLs indexadas |

LinkedIn, cidade e menção a IA ficaram vazios: o Instagram anônimo respondeu 429 antes de ler a bio, e as páginas não trouxeram esses dados. Não há `não` em `menciona_ia` porque não houve texto longo o bastante para afirmar ausência.

O Instaloader anônimo levou HTTP 429 na primeira ficha (`contadoraldodiasmentor`) e parou. Sem o segredo `IG_USERNAME` / `IG_SESSIONFILE`, é o comportamento esperado em IP de datacenter.

DuckDuckGo HTML respondeu 202 (página de anomalia) nas duas consultas e foi desligado. O Yahoo Brasil devolveu 14 resultados e depois HTTP 500; o job parou nas duas fontes. Por isso o CSV do dia tem 3 linhas, não 20. Vinte é o teto. Num runner novo, uma vez por dia, a mesma consulta tende a render mais, porque este IP já tinha sido usado várias vezes seguidas para testar o fluxo.

Antes desse bloqueio, uma passagem anterior (sobrescrita quando os buscadores passaram a falhar) tinha montado uma lista maior e ainda dentro do filtro: Simone Martins, Jéssica Romualdo, Fernanda Oliveira, Fernanda KZ, Willer Alfaia, Helô de Castro, Pedro Nery, Marcelo Bianchi e Instituto DNA Contábil, além de Aldo, Silvio e Fernando. Essa lista não está no CSV atual. Nomes grandes e páginas que não são oferta (blog "guia completo", login de aluno, produto de mentoria para MEI, espelho imginn) foram descartados de propósito.

`data/mentores_master.csv` começa com as 20 pessoas do funil anexo e só então recebe os novos. Elas não voltam na busca.
