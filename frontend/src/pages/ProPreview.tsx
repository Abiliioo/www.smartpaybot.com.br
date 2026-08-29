import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { PlanCard } from '../components/PlanCard'
import { SectionHeader } from '../components/SectionHeader'
import { faqs } from '../api/mockData'
import type { PreviewView } from '../types'

type ProPreviewProps = {
  onNavigate: (view: PreviewView) => void
}

export function ProPreview({ onNavigate }: ProPreviewProps) {
  return (
    <main className="spb-preview-page spb-pro-preview">
      <section className="spb-pro-hero spb-pro-hero--premium">
        <div>
          <p className="spb-kicker">SmartPayBot Pro</p>
          <h1>Mais keywords, mais alertas, menos cortes no monitoramento.</h1>
          <p>O Pro remove os limites do Free para quem acompanha oportunidades todos os dias.</p>
          <div className="spb-hero-actions">
            <Button>Quero o Pro</Button>
            <Button variant="secondary" onClick={() => onNavigate('landing')}>Voltar para a Home</Button>
          </div>
        </div>
        <Card tone="accent" className="spb-price-focus spb-price-focus--premium">
          <span>Pro</span>
          <strong>R$ 47</strong>
          <small>por mês</small>
          <ul>
            <li>Keywords ilimitadas</li>
            <li>Alertas ilimitados</li>
            <li>Suporte via WhatsApp</li>
          </ul>
          <Button>Quero o Pro</Button>
        </Card>
      </section>

      <section>
        <SectionHeader title="Free vs Pro" copy="Comparação objetiva para decidir quando os limites começam a atrapalhar." />
        <div className="spb-plan-grid">
          <PlanCard
            name="Free"
            price="R$ 0"
            caption="bom para testar"
            features={['3 keywords', '10 alertas por dia', 'Sem suporte prioritário']}
            cta="Voltar ao dashboard"
            onClick={() => onNavigate('dashboard')}
          />
          <PlanCard
            name="Pro"
            price="R$ 47"
            caption="para operar sem limite"
            features={['Keywords ilimitadas', 'Alertas ilimitados', 'Suporte via WhatsApp']}
            cta="Fazer upgrade"
            featured
          />
        </div>
      </section>

      <section>
        <SectionHeader title="Quando faz sentido assinar" copy="Upgrade como continuidade do uso, não como promessa de resultado." />
        <div className="spb-three-grid">
          <Card><h3>Você monitora mais de um serviço</h3><p>Cadastre várias especialidades sem escolher qual área fica de fora.</p></Card>
          <Card><h3>Os 10 alertas acabam cedo</h3><p>O Pro mantém o fluxo de alertas sem corte diário artificial.</p></Card>
          <Card><h3>O produto virou rotina</h3><p>Suporte direto ajuda quando Telegram, keywords ou operação precisam de ajuste.</p></Card>
        </div>
      </section>

      <section>
        <SectionHeader title="Como ativa" copy="Um fluxo direto para sair do Free sem trocar de produto." />
        <div className="spb-flow-grid spb-flow-grid--compact">
          <Card tone="quiet" className="spb-flow-card"><span>01</span><h3>Peça o Pro</h3><p>O CTA abre o contato de upgrade preservado pelo fluxo atual.</p></Card>
          <Card tone="quiet" className="spb-flow-card"><span>02</span><h3>Combine o Pix</h3><p>Pagamento e ativação seguem o processo operacional atual.</p></Card>
          <Card tone="quiet" className="spb-flow-card"><span>03</span><h3>Use sem corte</h3><p>Keywords e alertas deixam de usar os limites do plano Free.</p></Card>
        </div>
      </section>

      <section>
        <SectionHeader title="Perguntas rápidas" />
        <div className="spb-faq-grid">
          {faqs.map(([question, answer]) => (
            <Card key={question} tone="quiet">
              <h3>{question}</h3>
              <p>{answer}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="spb-final-cta">
        <SectionHeader title="Pronto para operar sem limite?" copy="Sem promessa de contratação: o ganho é reduzir busca manual e ampliar cobertura de alertas." />
        <div className="spb-hero-actions">
          <Button>Quero o Pro</Button>
          <Button variant="secondary" onClick={() => onNavigate('landing')}>Criar conta grátis</Button>
        </div>
      </section>
    </main>
  )
}
