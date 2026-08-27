import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { PlanCard } from '../components/PlanCard'
import { SectionHeader } from '../components/SectionHeader'
import { StepCard } from '../components/StepCard'
import type { PreviewView } from '../types'

type LandingPreviewProps = {
  onNavigate: (view: PreviewView) => void
  realLanding?: boolean
}

export function LandingPreview({ onNavigate, realLanding = false }: LandingPreviewProps) {
  return (
    <main className="spb-preview-page">
      <section className="spb-hero-grid">
        <div className="spb-hero-copy">
          <p className="spb-kicker">Alertas de freelas em tempo quase real</p>
          <h1>Chegue primeiro nas oportunidades que combinam com voce.</h1>
          <p>
            O SmartPayBot monitora o 99Freelas, filtra pelo seu perfil e entrega no Telegram
            um alerta claro para voce decidir rapido.
          </p>
          <div className="spb-hero-actions">
            {realLanding ? (
              <>
                <Button href="/auth/register">Comecar gratis</Button>
                <Button variant="secondary" href="/auth/login">Entrar</Button>
              </>
            ) : (
              <>
                <Button onClick={() => onNavigate('dashboard')}>Ver dashboard</Button>
                <Button variant="secondary" onClick={() => onNavigate('pro')}>Conhecer Pro</Button>
              </>
            )}
          </div>
        </div>

        <Card className="spb-alert-preview">
          <div className="spb-alert-preview__top">
            <span>Novo projeto</span>
            <strong>ha 4 min</strong>
          </div>
          <h2>Automacao de planilha para controle de estoque</h2>
          <dl>
            <div><dt>Keyword</dt><dd>Excel</dd></div>
            <div><dt>Propostas</dt><dd>3</dd></div>
            <div><dt>Cliente</dt><dd>4.8 / 5</dd></div>
          </dl>
          <Button variant="secondary" href={realLanding ? '/dashboard/' : undefined}>
            Abrir oportunidade
          </Button>
        </Card>
      </section>

      <section>
        <SectionHeader
          eyebrow="Por que existe"
          title="Menos garimpo manual, mais tempo propondo."
          copy="A UI nova prioriza clareza, velocidade e uma sensacao de produto confiavel."
        />
        <div className="spb-three-grid">
          {['Monitorar manualmente custa foco', 'Chegar tarde reduz conversao', 'Filtro ruim vira ruido'].map((item) => (
            <Card key={item} tone="quiet">
              <h3>{item}</h3>
              <p>O preview trata cada dor como um bloco curto, alinhado e facil de escanear.</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <SectionHeader title="Como funciona" copy="Tres passos pequenos, com CTA sempre claro." />
        <div className="spb-step-grid">
          <StepCard step="01" title="Configure keywords" copy="Escolha termos que representam seu trabalho real." />
          <StepCard step="02" title="Conecte Telegram" copy="Use um codigo unico e mantenha a sessao segura no Flask." />
          <StepCard step="03" title="Receba e aja" copy="Veja contexto suficiente para abrir o projeto certo." />
        </div>
      </section>

      <section>
        <SectionHeader title="Planos" copy="Free para provar valor, Pro para remover limites." />
        <div className="spb-plan-grid">
          <PlanCard
            name="Free"
            price="R$ 0"
            caption="para comecar"
            features={['3 keywords', '10 alertas por dia', 'Dashboard essencial']}
            cta="Comecar gratis"
            href={realLanding ? '/auth/register' : undefined}
          />
          <PlanCard
            name="Pro"
            price="R$ 47"
            caption="por mes"
            features={['Keywords ilimitadas', 'Alertas ilimitados', 'Suporte prioritario']}
            cta="Ver upgrade"
            featured
            href={realLanding ? '/pro' : undefined}
            onClick={realLanding ? undefined : () => onNavigate('pro')}
          />
        </div>
      </section>
    </main>
  )
}
