import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { PlanCard } from '../components/PlanCard'
import { SectionHeader } from '../components/SectionHeader'
import type { PreviewView } from '../types'

type ProPreviewProps = {
  onNavigate: (view: PreviewView) => void
}

const proFaqs = [
  ['Preciso assinar para começar?', 'Não. Você pode usar o Free com limites e fazer upgrade quando fizer sentido.'],
  ['O Pro garante projetos?', 'Não. O Pro amplia sua cobertura de monitoramento, mas a proposta e a negociação continuam sendo suas.'],
  ['Como funciona o pagamento?', 'O upgrade é combinado pelo canal de atendimento atual, com ativação após confirmação.'],
  ['Posso cancelar?', 'Sim. O plano pode ser interrompido conforme o acordo de atendimento.'],
]

export function ProPreview({ onNavigate }: ProPreviewProps) {
  return (
    <main className="spb-preview-page spb-pro-preview spb-250k-pro spb-pro-upgrade-page">
      <section className="spb-pro-upgrade-hero">
        <div className="spb-250k-pro-copy">
          <p className="spb-kicker">SmartPayBot Pro</p>
          <h1>Quando o Free corta sua rotina, o Pro mantém os alertas chegando.</h1>
          <p>Monitore mais palavras-chave, receba alertas sem limite diário e mantenha o fluxo de oportunidades ativo.</p>
          <div className="spb-hero-actions">
            <Button>Quero o Pro</Button>
            <Button variant="secondary" onClick={() => onNavigate('landing')}>Começar grátis</Button>
          </div>
        </div>

        <Card tone="accent" className="spb-pro-price-summary">
          <div>
            <span>Pro</span>
            <strong>R$ 47</strong>
            <small>por mês</small>
          </div>
          <ul>
            <li>Palavras-chave ilimitadas</li>
            <li>Alertas ilimitados</li>
            <li>Suporte via WhatsApp</li>
          </ul>
          <Button>Fazer upgrade</Button>
        </Card>
      </section>

      <section className="spb-pro-use-section">
        <SectionHeader title="O que muda na prática" copy="O Pro aumenta cobertura quando monitorar oportunidades deixa de ser teste e vira rotina." />
        <div className="spb-pro-change-grid">
          <Card tone="quiet"><h3>Mais cobertura</h3><p>Acompanhe mais áreas e termos sem escolher o que fica de fora.</p></Card>
          <Card tone="quiet"><h3>Menos pausa por limite</h3><p>Os alertas continuam chegando ao longo do dia.</p></Card>
          <Card tone="quiet"><h3>Mais liberdade para testar</h3><p>Experimente novas palavras-chave sem travar o monitoramento principal.</p></Card>
          <Card tone="quiet"><h3>Suporte direto</h3><p>Conte com atendimento para ajustes de rotina, Telegram e plano.</p></Card>
        </div>
      </section>

      <section className="spb-250k-compare-section spb-pro-plan-section">
        <SectionHeader title="Free vs Pro" copy="Escolha pelo seu ritmo de uso, não por promessa de resultado." />
        <div className="spb-plan-grid spb-250k-plan-grid">
          <PlanCard
            name="Free"
            price="R$ 0"
            caption="bom para testar"
            features={['3 palavras-chave', '10 alertas por dia', 'Painel essencial']}
            cta="Voltar ao painel"
            onClick={() => onNavigate('dashboard')}
          />
          <PlanCard
            name="Pro"
            price="R$ 47"
            caption="para operar sem limite"
            features={['Palavras-chave ilimitadas', 'Alertas ilimitados', 'Suporte via WhatsApp']}
            cta="Fazer upgrade"
            featured
          />
        </div>
      </section>

      <section className="spb-250k-upgrade-section spb-pro-when-section">
        <Card tone="quiet" className="spb-250k-upgrade-copy">
          <span className="spb-mini-label">Quando faz sentido assinar</span>
          <h2>O Pro entra quando o monitoramento começa a fazer parte da rotina.</h2>
          <p>Você continua decidindo onde propor. O plano só remove os limites que atrapalham a cobertura.</p>
        </Card>
        <div className="spb-250k-upgrade-list">
          <article><span>01</span><strong>Você acompanha mais de uma área</strong><p>Monitore especialidades diferentes sem deixar termos importantes pausados.</p></article>
          <article><span>02</span><strong>Os 10 alertas acabam cedo</strong><p>Evite parar o acompanhamento justamente nos dias com mais movimento.</p></article>
          <article><span>03</span><strong>O monitoramento virou rotina diária</strong><p>Mantenha o fluxo ativo com mais liberdade para ajustar palavras-chave.</p></article>
        </div>
      </section>

      <section className="spb-250k-activation-section">
        <SectionHeader title="Como ativa" copy="Um caminho curto para sair do Free sem trocar de produto." />
        <div className="spb-250k-flow-line spb-250k-flow-line--three spb-250k-flow-line--calm">
          <article><span>01</span><h3>Peça o Pro</h3><p>Use o botão de upgrade e siga pelo atendimento atual.</p></article>
          <article><span>02</span><h3>Combine o pagamento</h3><p>Pagamento e ativação seguem o processo operacional existente.</p></article>
          <article><span>03</span><h3>Use sem corte</h3><p>Palavras-chave e alertas deixam de usar os limites do Free.</p></article>
        </div>
      </section>

      <section>
        <SectionHeader title="Perguntas rápidas" />
        <div className="spb-faq-grid spb-250k-faq-grid">
          {proFaqs.map(([question, answer]) => (
            <Card key={question} tone="quiet">
              <h3>{question}</h3>
              <p>{answer}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="spb-final-cta spb-250k-final-cta">
        <SectionHeader title="Monitore sem limite diário" copy="Amplie suas palavras-chave e mantenha os alertas ativos ao longo do dia." />
        <div className="spb-hero-actions">
          <Button>Quero o Pro</Button>
          <Button variant="secondary" onClick={() => onNavigate('landing')}>Criar conta grátis</Button>
        </div>
      </section>
    </main>
  )
}