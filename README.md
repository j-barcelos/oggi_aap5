# Sistema Web de Gestão de Reservas e Locação de Carrinhos de Sorvete

Protótipo de sistema web para centralizar a reserva e a locação de carrinhos refrigerados de sorvete para festas e eventos, com painel administrativo autenticado e dashboard analítico.

Desenvolvido para a **Oggi Sorvetes Barueri — Hevon Comércio LTDA** como Projeto Interdisciplinar V do 5º semestre de Gestão de Tecnologia da Informação (Fatec).

![Status](https://img.shields.io/badge/status-prot%C3%B3tipo-yellow)
![Python](https://img.shields.io/badge/python-3.x-blue)
![Django](https://img.shields.io/badge/django-MVT-092E20)
![MySQL](https://img.shields.io/badge/mysql-8.x-4479A1)
![Licença](https://img.shields.io/badge/licen%C3%A7a-acad%C3%AAmica-lightgrey)

---

## Sumário

- [Visão geral](#visão-geral)
- [O problema](#o-problema)
- [Funcionalidades](#funcionalidades)
- [Regras de negócio](#regras-de-negócio)
- [Stack tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Modelo de dados](#modelo-de-dados)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Execução](#execução)
- [API](#api)
- [Testes](#testes)
- [Privacidade e LGPD](#privacidade-e-lgpd)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Escopo e limitações](#escopo-e-limitações)
- [Roadmap](#roadmap)
- [Equipe](#equipe)
- [Metodologia](#metodologia)

---

## Visão geral

A loja mantém uma frota de carrinhos refrigerados alugados para festas, empresas e eventos da região de Barueri (SP). O controle da agenda é feito hoje de forma manual, por conversas no WhatsApp e anotações em papel, o que gera reservas duplicadas, venda acima do estoque, cálculos de valor sujeitos a erro e ausência total de indicadores.

Este sistema substitui esse controle difuso por um fluxo digital único, no qual a própria aplicação valida prazo mínimo, disponibilidade da frota, estoque e composição de preço antes de registrar a solicitação.

> **Natureza do projeto:** protótipo acadêmico, executado localmente, com banco MySQL de desenvolvimento e dados de teste. Não está implantado em nuvem comercial.

## O problema

| Aspecto | Situação atual |
|---|---|
| Solicitação | Mensagens no WhatsApp, sem canal único |
| Disponibilidade | Conferida manualmente em caderno de papel |
| Precificação | Calculada na hora, com calculadora |
| Confirmação | Anotação manual, sujeita a rasura e esquecimento |
| Histórico | Inexistente — impossível apurar receita ou sazonalidade |

**Impactos:** reservas duplicadas para a mesma data, risco de venda acima do estoque, retrabalho para remarcar eventos, desgaste com o cliente em datas comemorativas e decisões de preço e de compra de frota sem base objetiva.

## Funcionalidades

### Área pública

- Catálogo de sabores ativos com foto, preço e estoque
- Seleção de quantidades por sabor, com validação na interface
- Calendário mensal de disponibilidade (livre / poucas vagas / esgotada / data passada)
- Seleção da quantidade de carrinhos limitada à capacidade livre do dia
- Resumo do pedido atualizado dinamicamente
- Modal de contato com dados do cliente e do evento
- Contrato de comodato com aceite obrigatório, liberado só após leitura integral
- Geração de link do WhatsApp com resumo formatado do pedido

### Painel administrativo

- Autenticação e restrição de rotas a perfil interno
- Dashboard de métricas: receita confirmada, receita pendente, ticket médio, ocupação média, série diária de ocupação e ranking de sabores
- Calendário de gestão e listagem de reservas com busca e filtro por status
- Alteração de status (pendente → confirmado / cancelado)
- Gestão de clientes, sabores e carrinhos
- Exportação da listagem filtrada em CSV e PDF

## Regras de negócio

As regras ficam encapsuladas nos métodos do modelo `Reserva`:

| Regra | Implementação |
|---|---|
| Antecedência mínima de 24 horas | `Reserva.validate()` bloqueia datas com menos de 24h |
| Limite por capacidade do dia | Quantidade solicitada ≤ carrinhos ativos − reservas confirmadas na data |
| Taxa de aluguel | `Reserva.taxa_aluguel()` aplica R$ 50,00 fixos para subtotal < R$ 300,00 |
| Isenção da taxa | Subtotal ≥ R$ 300,00 zera a taxa |
| Total do pedido | `Reserva.total_pedido()` = subtotal + aluguel |
| Baixa de estoque | Ocorre apenas na transição para `confirmado`, nunca na criação |
| Mensagem padronizada | `Reserva.gerar_link_whatsapp()` monta o resumo com valores discriminados e aviso de frete à parte |

## Stack tecnológica

- **Linguagem:** Python 3
- **Framework web:** Django (padrão MVT)
- **Banco de dados:** MySQL
- **Front-end:** Django Template Language, CSS e JavaScript puro, layout responsivo
- **Relatórios:** geração de CSV e PDF
- **Versionamento de esquema:** Django migrations (0001–0010)

## Arquitetura

Aplicação em três camadas, seguindo o padrão MVT do Django:

```
Apresentação  →  templates HTML, CSS, JS
Negócio       →  models, views, api.py, regras de validação
Persistência  →  MySQL via Django ORM
Integração    →  links de WhatsApp (sem gateway de pagamento ou API de mapas)
```

Princípios aplicados: separação de responsabilidades, transação única na criação da reserva e dos itens, `select_related`/`prefetch_related` nas consultas do painel, credenciais fora do código.

## Modelo de dados

| Entidade | Atributos principais | Relacionamentos |
|---|---|---|
| `Carrinho` | id, preco_diaria, status | Associável a várias reservas ao longo do tempo |
| `Sorvete` | id, nome_sorvete, preco, quantidade, imagem, ativo | Aparece em vários itens de reserva (N:N via item) |
| `Cliente` | id, nome_cliente, endereco, telefone, email | Possui múltiplas reservas (1:N) |
| `Reserva` | id, id_cliente, id_carrinho, data_evento, valor_pedido, status, descricao | Pertence a um cliente, associa-se a um carrinho, possui vários itens (1:N) |
| `ReservaProduto` | id, id_reserva, id_sorvete, quantidade_escolhida | Refere-se a uma reserva e a um sabor |

## Instalação

Pré-requisitos: Python 3.10+, MySQL 8+, Git.

```bash
# 1. Clonar o repositório
git clone https://github.com/j-barcelos/oggi_aap5/
cd oggi_aap5

# 2. Criar e ativar o ambiente virtual
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Criar o banco de dados
mysql -u root -p -e "CREATE DATABASE oggi_reservas CHARACTER SET utf8mb4;"

# 5. Configurar variáveis de ambiente (ver seção abaixo)

# 6. Aplicar as migrations
python manage.py migrate

# 7. Criar usuário administrador
python manage.py createsuperuser
```

## Configuração

Crie um arquivo `.env` na raiz (ignorado pelo versionamento):

```env
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=True
DB_NAME=oggi_reservas
DB_USER=root
DB_PASSWORD=senha
DB_HOST=127.0.0.1
DB_PORT=3306
```

Nenhuma credencial deve ser commitada. O arquivo `.env` precisa constar no `.gitignore`.

## Execução

```bash
python manage.py runserver
```

- Área pública: `http://127.0.0.1:8000/`
- Painel administrativo: `http://127.0.0.1:8000/painel/`
- Dashboard: `http://127.0.0.1:8000/painel/dashboard/`

## API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/sabores/` | Lista sabores ativos |
| `GET` | `/api/disponibilidade/?mes=&ano=` | Ocupação por dia do mês |
| `POST` | `/api/reservas/` | Cria reserva com validação de prazo e capacidade |
| `GET` | `/api/reservas/<id>/whatsapp/` | Gera link do WhatsApp com o resumo |

Rotas do painel exigem sessão autenticada e perfil interno. Todas as requisições `POST` são protegidas por token CSRF.

## Testes

```bash
python manage.py test
```

Cenários cobertos:

1. Reserva válida com antecedência suficiente → criada, link gerado
2. Tentativa com menos de 24h → bloqueada
3. Data esgotada → marcada como esgotada, seletor oculto
4. Subtotal ≥ R$ 300,00 → aluguel isento
5. Subtotal < R$ 300,00 → taxa fixa de R$ 50,00 aplicada
6. Envio sem aceite do contrato → botão desabilitado
7. Confirmação de reserva → baixa de estoque proporcional

## Privacidade e LGPD

Dados tratados: nome completo, telefone, endereço do evento e e-mail opcional. Nenhum dado sensível é coletado.

- **Finalidade:** contato, localização para entrega/retirada e formalização do contrato de comodato
- **Minimização:** apenas campos necessários; e-mail facultativo
- **Controle de acesso:** dados visíveis somente a administradores autenticados
- **Transparência:** aviso de privacidade no formulário e cláusula LGPD no contrato
- **Retenção:** registros mantidos por interesse legítimo e obrigação contratual

## Estrutura do projeto

```
├── manage.py
├── requirements.txt
├── .env.example
├── templates/            # index.html, painel.html, dashboard.html
├── static/               # CSS, JavaScript (painel.js)
├── <app>/
│   ├── models.py         # Carrinho, Sorvete, Cliente, Reserva, ReservaProduto
│   ├── views.py
│   ├── api.py
│   ├── dashboard.py
│   ├── urls.py
│   └── migrations/       # 0001 … 0010
└── tests/
```

## Escopo e limitações

**Não contemplado:** gateway de pagamento ou Pix automático, nota fiscal eletrônica, cálculo de frete por API de mapas, rastreamento veicular, aplicativo nativo, estoque de insumos e gestão de contratos de terceiros.

**Limitações conhecidas:** validação em ambiente local com dados fictícios ou fornecidos pela loja, sem implantação em nuvem; frete cotado à parte com transportadora; sem notificações por e-mail ou SMS; sem política automática de exclusão de dados pessoais nem backup programado.

## Roadmap

- [ ] Política automática de retenção e exclusão de dados pessoais
- [ ] Rotina de backup programado
- [ ] Notificações automáticas por e-mail ou SMS
- [ ] Integração com API de mapas para cotação de frete
- [ ] Gateway de pagamento / Pix automático
- [ ] Implantação em servidor público com HTTPS
- [ ] Teste de usabilidade com clientes finais

## Equipe

| Papel | Integrantes |
|---|---|
| Scrum Master, coordenação e prazos; back-end | Vinicius Monteiro dos Santos |
| Front-end; back-end e banco de dados | João Emanuel de Bezerra Barcelos |
| Documentação, regras de negócio e testes | Geovana Lopes de Sousa, Eduardo Garcia Dantas |
| Professor orientador | Bruno Figueiredo dos Santos |

## Metodologia

Pesquisa exploratória e diagnóstico, análise documental, modelagem de processos As-Is e To-Be com técnica Makigami, e desenvolvimento ágil em quatro sprints quinzenais com quadro Kanban e revisão ao fim de cada ciclo.

---

Projeto acadêmico desenvolvido na Fatec — 5º semestre de Gestão de Tecnologia da Informação.
