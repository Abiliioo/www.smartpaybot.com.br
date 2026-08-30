import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { PlanCard } from '../components/PlanCard'
import { SectionHeader } from '../components/SectionHeader'
import type { PreviewView } from '../types'

type LandingPreviewProps = {
  onNavigate: (view: PreviewView) => void
  realLanding?: boolean
}

export function LandingPreview({ onNavigate, realLanding = false }: LandingPreviewProps) {
  return (
    <main className={`spb-preview-page spb-250k-home ${realLanding ? 'spb-preview-page--landing' : 'spb-preview-page--preview'}`}>
      <section className="spb-250k-hero" aria-labelledby="landing-title">
        <div className="spb-250k-hero__copy">
          <p className="spb-kicker">Monitoramento para freelancers</p>
          <h1 id="landing-title">Alertas de freelas direto no Telegram, sem garimpo manual.</h1>
          <p>
            Cadastre palavras-chave, receba oportunidades compatíveis e revise tudo em um painel simples antes de decidir.
          </p>
          <div className="spb-hero-actions">
            {realLanding ? (
              <>
                <Button href="/auth/register">Começar grátis</Button>
                <Button variant="secondary" href="/pro">Conhecer Pro</Button>
              </>
            ) : (
              <>
                <Button onClick={() => onNavigate('dashboard')}>Ver painel</Button>
                <Button variant="secondary" onClick={() => onNavigate('pro')}>Conhecer Pro</Button>
              </>
            )}
          </div>
          <div className="spb-250k-trust" aria-label="Garantias do produto">
            <span>Produto independente</span>
            <span>Sem promessa de contratação</span>
            <span>Alertas por palavras-chave</span>
          </div>
        </div>

        <div className="spb-250k-product-stage" aria-label="Fluxo visual do SmartPayBot">
          <Card className="spb-250k-alert-card">
            <div className="spb-250k-card-topline">
              <span>Telegram conectado</span>
              <strong>Novo alerta</strong>
            </div>
            <h2>Automação de planilha para controle de estoque</h2>
            <p>Projeto filtrado pelos seus termos para você revisar com contexto antes de abrir a proposta.</p>
            <div className="spb-250k-alert-meta" aria-label="Resumo do alerta">
              <span><small>Termo</small><strong>Excel</strong></span>
              <span><small>Canal</small><strong>Telegram</strong></span>
              <span><small>Próximo passo</small><strong>Painel</strong></span>
            </div>
            <Button variant="secondary" href={realLanding ? '/dashboard/' : undefined} onClick={realLanding ? undefined : () => onNavigate('dashboard')}>
              Ver no painel
            </Button>
          </Card>

          <div className="spb-250k-side-stack">
            <Card tone="quiet" className="spb-250k-keyword-card">
              <span className="spb-mini-label">Palavra-chave monitorada</span>
              <strong>Excel</strong>
              <div className="spb-250k-signal-chart" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            </Card>

            <Card tone="accent" className="spb-250k-plan-card">
              <span className="spb-mini-label">Plano atual</span>
              <strong>Free</strong>
              <p>3 palavras-chave e 10 alertas por dia. Pro remove esses limites.</p>
            </Card>
          </div>
        </div>
      </section>

      <section className="spb-250k-split-section">
        <SectionHeader
          eyebrow="Por que existe"
          title="Menos busca repetitiva, mais clareza para agir."
          copy="O SmartPayBot organiza sinais recorrentes de oportunidade para você gastar energia na decisão, não no garimpo manual."
        />
        <div className="spb-250k-editorial-card">
          <Card tone="quiet"><h3>Foco por termos</h3><p>Você escolhe os serviços e nichos que quer acompanhar.</p></Card>
          <Card tone="quiet"><h3>Alerta no canal certo</h3><p>O Telegram avisa sem exigir que você fique atualizando listas.</p></Card>
          <Card tone="quiet"><h3>Decisão no painel</h3><p>O painel mantém contexto suficiente para priorizar com calma.</p></Card>
        </div>
      </section>

      <section className="spb-250k-flow-section">
        <SectionHeader title="Do termo monitorado à decisão" copy="Um fluxo simples, sem promessa de resultado garantido." />
        <div className="spb-250k-flow-line">
          {[
            ['01', 'Palavra-chave', 'Cadastre termos ligados ao seu trabalho.'],
            ['02', 'Alerta', 'Receba a oportunidade quando ela combina.'],
            ['03', 'Painel', 'Revise o contexto em um lugar só.'],
            ['04', 'Decisão', 'Abra apenas quando fizer sentido.'],
          ].map(([step, title, copy]) => (
            <article key={step}>
              <span>{step}</span>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="spb-250k-plans-section">
        <SectionHeader title="Comece leve. Expanda quando virar rotina." copy="Free valida o fluxo. Pro remove limites para quem monitora mais termos todos os dias." />
        <div className="spb-plan-grid spb-250k-plan-grid">
          <PlanCard
            name="Free"
            price="R$ 0"
            caption="para começar"
            features={['3 palavras-chave', '10 alertas por dia', 'Painel essencial']}
            cta="Começar grátis"
            href={realLanding ? '/auth/register' : undefined}
            onClick={realLanding ? undefined : () => onNavigate('dashboard')}
          />
          <PlanCard
            name="Pro"
            price="R$ 47"
            caption="por mês"
            features={['Palavras-chave ilimitadas', 'Alertas ilimitados', 'Mais flexibilidade para operar']}
            cta="Conhecer Pro"
            featured
            href={realLanding ? '/pro' : undefined}
            onClick={realLanding ? undefined : () => onNavigate('pro')}
          />
        </div>
      </section>

      <section className="spb-250k-proof-section">
        <Card tone="quiet" className="spb-250k-proof-main">
          <span className="spb-mini-label">Credibilidade</span>
          <h2>O SmartPayBot organiza sinais. A decisão continua sendo sua.</h2>
          <p>Sem vínculo oficial com plataformas e sem promessa de contratação: o produto reduz trabalho repetitivo para você avaliar cada oportunidade com mais calma.</p>
        </Card>
        <div className="spb-250k-proof-list">
          <span>Independente</span>
          <span>Recorrente</span>
          <span>Objetivo</span>
        </div>
      </section>

      <section className="spb-final-cta spb-250k-final-cta">
        <SectionHeader title="Comece pelo essencial" copy="Teste o Free, conecte seu Telegram e evolua para o Pro quando os limites começarem a pesar." />
        <div className="spb-hero-actions">
          <Button href={realLanding ? '/auth/register' : undefined} onClick={realLanding ? undefined : () => onNavigate('dashboard')}>Começar grátis</Button>
          <Button variant="secondary" href={realLanding ? '/pro' : undefined} onClick={realLanding ? undefined : () => onNavigate('pro')}>Conhecer Pro</Button>
        </div>
      </section>
    </main>
  )
}
