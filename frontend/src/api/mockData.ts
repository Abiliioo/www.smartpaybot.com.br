export const statusMetrics = [
  { label: 'Alertas hoje', value: '8/10', detail: '2 antes do limite Free', tone: 'amber' as const },
  { label: 'Palavras-chave ativas', value: '3/3', detail: 'Free em uso', tone: 'blue' as const },
  { label: 'Para revisar', value: '4', detail: 'oportunidades recentes', tone: 'green' as const },
  { label: 'Última atualização', value: 'há 4 min', detail: 'Telegram recebendo', tone: 'neutral' as const },
]

export const metrics = statusMetrics

export const keywords = ['Python', 'Excel', 'Automacao', 'WordPress', 'Power BI']

export const activeKeywords = ['Python', 'Excel', 'Power BI']

export const pausedKeywords = ['Automacao', 'WordPress']

export const opportunities = [
  {
    title: 'Dashboard financeiro em Power BI',
    keyword: 'Power BI',
    age: '4 min',
    proposals: 2,
    priority: 'Alta aderência',
    summary: 'Pedido direto, escopo claro e poucas propostas até agora.',
  },
  {
    title: 'Automação de planilha Excel',
    keyword: 'Excel',
    age: '11 min',
    proposals: 5,
    priority: 'Boa chance',
    summary: 'Rotina administrativa com entrega objetiva e linguagem familiar.',
  },
  {
    title: 'Integração simples entre formulários e planilhas',
    keyword: 'Python',
    age: '18 min',
    proposals: 8,
    priority: 'Revisar com calma',
    summary: 'Pode valer proposta se o prazo e o acesso estiverem claros.',
  },
]

export const recentProjects = opportunities

export const homeSignals = [
  ['Telegram conectado', 'Último alerta há 4 min'],
  ['Limite Free', '8 de 10 alertas usados'],
  ['Próxima ação', 'Revisar 4 oportunidades'],
]

export const faqs = [
  ['Preciso assinar para começar?', 'Nao. Você pode usar o Free com limites e fazer upgrade quando fizer sentido.'],
  ['O Pro garante que vou fechar projetos?', 'Nao. O Pro amplia sua cobertura de monitoramento, mas a proposta e a negociacao continuam sendo suas.'],
  ['Como funciona o pagamento?', 'O upgrade é combinado pelo canal de atendimento atual, com ativacao apos confirmacao.'],
  ['Posso cancelar?', 'Sim. O plano pode ser interrompido conforme o acordo de atendimento.'],
]