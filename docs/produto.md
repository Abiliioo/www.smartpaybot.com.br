# SmartPayBot — Documento de Produto

## O que é

O SmartPayBot é um **monitor de oportunidades de freelas** com alertas em tempo real via Telegram. O usuário cadastra palavras-chave (ex.: "Excel", "Python", "WordPress") e o bot escaneia o 99Freelas periodicamente, enviando uma notificação no Telegram assim que um projeto compatível aparecer.

---

## Problema resolvido

Freelancers que dependem de plataformas como 99Freelas perdem oportunidades porque:

1. **Não ficam monitorando a plataforma o dia todo** — têm projetos em andamento.
2. **Chegam tarde** — quando veem uma vaga, já há 10+ propostas.
3. **Não filtram com precisão** — perdem tempo vendo vagas irrelevantes.

O SmartPayBot resolve os três: monitora 24/7, avisa em segundos e filtra pelo que o freelancer faz.

---

## Público-alvo

**Primário:** Freelancers brasileiros ativos no 99Freelas que:
- Trabalham nas áreas de tecnologia, design, redação ou finanças.
- Enviam mais de 5 propostas por semana.
- Já usam Telegram (adoção altíssima no público tech BR).
- Estão dispostos a pagar R$ 30–60/mês por uma vantagem competitiva.

**Secundário (futuro):** Agências e profissionais que monitoram múltiplas plataformas.

---

## Proposta de valor

> *"Seja o primeiro a ver — e o primeiro a propor."*

- **Velocidade:** alertas em minutos após publicação (não horas).
- **Precisão:** filtro por palavras-chave relevantes ao seu perfil.
- **Inteligência:** enriquecimento automático (propostas já recebidas, reputação do cliente, tempo de publicação).
- **Simplicidade:** configura em 2 minutos, funciona sozinho depois.

---

## Diferenciais

| Concorrente / Alternativa | Limitação | SmartPayBot |
|---|---|---|
| Verificar 99Freelas manualmente | Lento, cansativo | Alerta automático |
| Ativar notificações da plataforma | Manda tudo, sem filtro | Filtra por keywords |
| Scripts caseiros | Instável, sem UI | Produto com dashboard |
| Ferramentas de IA genéricas | Caro, complexo | Foco no 99Freelas BR |

---

## Funcionalidades atuais (MVP)

- Cadastro e login de usuário.
- Cadastro de palavras-chave (até 3 no Free, ilimitado no Pro).
- Vinculação do Telegram via deep-link ou código `/start`.
- Pipeline automático: scraping → matching → notificação Telegram.
- Enriquecimento de alertas (propostas enviadas, reputação do cliente).
- Dashboard com KPIs (projetos hoje/ontem/semana, receita de freelas ganhos).
- Rastreamento de projetos ganhos (won/lost, valor em R$).
- Controle ON/OFF do pipeline no dashboard.
- Painel admin para gestão manual de planos.

---

## Visão de MVP beta pago

O objetivo imediato é ter **10 usuários pagando R$ 47/mês** com gestão manual:

1. Usuário se cadastra normalmente.
2. Admin eleva o plano para Pro manualmente no painel `/admin/`.
3. Usuário paga via Pix/transferência.
4. Receita inicial = validação do modelo de negócio.

Esse modelo manual é temporário até a integração com Stripe ser priorizada.

---

## Roadmap de produto (macro)

| Fase | Objetivo | Estado |
|---|---|---|
| 0 | Pipeline funcional de scraping + notificação | ✅ Feito |
| 1 | Sistema de planos Free/Pro + admin | ✅ Feito |
| 2 | Beta pago manual (10 usuários pagantes) | 🔄 Em andamento |
| 3 | Stripe Checkout + webhooks de pagamento | ⏳ Próximo |
| 4 | Landing page pública com preços | ⏳ Próximo |
| 5 | Suporte a outras plataformas (Workana, GetNinjas) | ⏳ Futuro |
| 6 | Filtros avançados (orçamento, categoria) | ⏳ Futuro |
| 7 | Relatório semanal de ROI por e-mail | ⏳ Futuro |
