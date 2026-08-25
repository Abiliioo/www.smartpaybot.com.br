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
      <section className="spb-pro-hero">
        <div>
          <p className="spb-kicker">SmartPayBot Pro</p>
          <h1>Remova limites quando as oportunidades comecarem a chegar.</h1>
          <p>Keywords ilimitadas, alertas ilimitados e suporte direto por R$ 47/mes.</p>
        </div>
        <Card tone="accent" className="spb-price-focus">
          <span>Pro</span>
          <strong>R$ 47</strong>
          <small>por mes</small>
          <Button>Quero o Pro</Button>
        </Card>
      </section>

      <section>
        <SectionHeader title="Free vs Pro" copy="Comparacao objetiva, sem hero gigante nem bloco vazio." />
        <div className="spb-plan-grid">
          <PlanCard
            name="Free"
            price="R$ 0"
            caption="bom para testar"
            features={['3 keywords', '10 alertas por dia', 'Sem suporte prioritario']}
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
        <SectionHeader title="Beneficios" copy="Cards alinhados e orientados a decisao." />
        <div className="spb-three-grid">
          <Card><h3>Mais cobertura</h3><p>Monitore varias especialidades sem escolher qual area sacrificar.</p></Card>
          <Card><h3>Mais velocidade</h3><p>Receba todos os alertas relevantes em dias de maior volume.</p></Card>
          <Card><h3>Mais confianca</h3><p>Suporte direto reduz atrito no momento em que o produto vira rotina.</p></Card>
        </div>
      </section>

      <section>
        <SectionHeader title="Perguntas rapidas" />
        <div className="spb-faq-grid">
          {faqs.map(([question, answer]) => (
            <Card key={question} tone="quiet">
              <h3>{question}</h3>
              <p>{answer}</p>
            </Card>
          ))}
        </div>
      </section>
    </main>
  )
}
