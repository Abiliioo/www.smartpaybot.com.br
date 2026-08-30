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
  ['O Pro garante que vou fechar projetos?', 'Não. O Pro amplia sua cobertura de monitoramento, mas a proposta e a negociação continuam sendo suas.'],
  ['Como funciona o pagamento?', 'O upgrade é combinado pelo canal de atendimento atual, com ativação após confirmação.'],
  ['Posso cancelar?', 'Sim. O plano pode ser interrompido conforme o acordo de atendimento.'],
]

export function ProPreview({ onNavigate }: ProPreviewProps) {
  return (
    <main className="spb-preview-page spb-pro-preview spb-250k-pro">
      <section className="spb-250k-pro-hero">
        <div className="spb-250k-pro-copy">
          <p className="spb-kicker">SmartPayBot Pro</p>
          <h1>Mais cobertura para quem monitora oportunidades todos os dias.</h1>
          <p>O Pro remove os limites do Free para acompanhar mais palavras-chave e receber alertas ao longo do dia.</p>
          <div className="spb-hero-actions">
            <Button>Quero o Pro</Button>
            <Button variant="secondary" onClick={() => onNavigate('landing')}>Voltar para a Home</Button>
          </div>
        </div>

        <Card tone="accent" className="spb-250k-price-card">
          <span>Pro</span>
          <strong>R$ 47</strong>
          <small>por mês</small>
          <ul>
            <li>Palavras-chave ilimitadas</li>
            <li>Alertas ilimitados</li>
            <li>Suporte via WhatsApp</li>
          </ul>
          <Button>Fazer upgrade</Button>
        </Card>
      </section>

      <section className="spb-250k-compare-section">
        <SectionHeader title="Free vs Pro" copy="A diferença aparece quando monitorar oportunidades deixa de ser teste e vira rotina." />
        <div className="spb-plan-grid spb-250k-plan-grid">
          <PlanCard
            name="Free"
            price="R$ 0"
            caption="bom para testar"
            features={['3 palavras-chave', '10 alertas por dia', 'Sem suporte prioritário']}
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

      <section className="spb-250k-upgrade-section">
        <Card tone="quiet" className="spb-250k-upgrade-copy">
          <span className="spb-mini-label">Quando faz sentido</span>
          <h2>Assine quando o limite estiver cortando seu monitoramento.</h2>
          <p>O ganho do Pro é ampliar cobertura e reduzir atrito para quem acompanha oportunidades com frequência.</p>
        </Card>
        <div className="spb-250k-upgrade-list">
          <article><span>01</span><strong>Você acompanha mais de uma especialidade</strong><p>Monitore áreas diferentes sem deixar um serviço importante de fora.</p></article>
          <article><span>02</span><strong>Os 10 alertas acabam cedo</strong><p>Continue recebendo oportunidades mesmo quando o Free chega ao limite diário.</p></article>
          <article><span>03</span><strong>A busca virou rotina diária</strong><p>Use suporte direto quando Telegram, palavras-chave ou rotina precisarem de ajuste.</p></article>
        </div>
      </section>

      <section className="spb-250k-activation-section">
        <SectionHeader title="Como ativa" copy="Um caminho curto para sair do Free sem trocar de produto." />
        <div className="spb-250k-flow-line spb-250k-flow-line--three spb-250k-flow-line--calm">
          <article><span>01</span><h3>Peça o Pro</h3><p>Comece pelo botão de upgrade e siga pelo atendimento atual.</p></article>
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
        <SectionHeader title="Pronto para monitorar sem limite?" copy="Amplie suas palavras-chave e mantenha os alertas chegando ao longo do dia." />
        <div className="spb-hero-actions">
          <Button>Quero o Pro</Button>
          <Button variant="secondary" onClick={() => onNavigate('landing')}>Criar conta grátis</Button>
        </div>
      </section>
    </main>
  )
}