import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { PlanCard } from '../components/PlanCard'
import { SectionHeader } from '../components/SectionHeader'
import { homeSignals } from '../api/mockData'
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
            <span>Você decide quando abrir proposta</span>
          </div>
        </div>

        <div className="spb-home-product" aria-label="Resumo visual do painel SmartPayBot">
          <Card className="spb-home-product__main">
            <div className="spb-250k-card-topline">
              <span>Painel de oportunidades</span>
              <strong>Monitoramento ativo</strong>
            </div>
            <h2>4 oportunidades para revisar agora</h2>
            <p>O alerta chega no Telegram. O painel mostra contexto, limite do plano e próximo passo antes de você abrir proposta.</p>
            <div className="spb-home-signal-list">
              {homeSignals.map(([label, value]) => (
                <span key={label}><small>{label}</small><strong>{value}</strong></span>
              ))}
            </div>
            <Button variant="secondary" href={realLanding ? '/dashboard/' : undefined} onClick={realLanding ? undefined : () => onNavigate('dashboard')}>
              Ver como funciona
            </Button>
          </Card>

          <Card tone="quiet" className="spb-home-opportunity-card">
            <span className="spb-mini-label">Alerta recebido</span>
            <strong>Power BI</strong>
            <p>Dashboard financeiro com poucas propostas e boa aderência.</p>
          </Card>
        </div>
      </section>

      <section className="spb-250k-split-section">
        <SectionHeader
          eyebrow="Como funciona"
          title="Do termo monitorado à proposta certa."
          copy="O fluxo foi pensado para tirar a busca repetitiva da rotina e deixar a decisão mais clara."
        />
        <div className="spb-250k-editorial-card spb-home-how-grid">
          <Card tone="quiet"><h3>1. Cadastre palavras-chave</h3><p>Escolha serviços, nichos e ferramentas que combinam com seu trabalho.</p></Card>
          <Card tone="quiet"><h3>2. Receba alertas</h3><p>O Telegram avisa quando aparece uma oportunidade compatível.</p></Card>
          <Card tone="quiet"><h3>3. Revise no painel</h3><p>Veja limite, contexto e prioridade antes de decidir abrir proposta.</p></Card>
        </div>
      </section>

      <section className="spb-250k-flow-section">
        <SectionHeader title="Por que usar" copy="Um produto simples para organizar oportunidades sem prometer resultado garantido." />
        <div className="spb-250k-flow-line spb-250k-flow-line--calm spb-home-benefits">
          {[
            ['Menos garimpo manual', 'Você não precisa ficar atualizando listas ao longo do dia.'],
            ['Mais contexto', 'Cada alerta chega com sinais úteis para decidir com calma.'],
            ['Limites claros', 'O Free mostra quando o uso está chegando ao corte diário.'],
            ['Upgrade natural', 'O Pro faz sentido quando o monitoramento vira rotina.'],
          ].map(([title, copy]) => (
            <article key={title}>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="spb-250k-plans-section">
        <SectionHeader title="Comece leve. Expanda quando virar rotina." copy="Free testa o fluxo. Pro mantém os alertas chegando quando o limite diário começa a atrapalhar." />
        <div className="spb-plan-grid spb-250k-plan-grid">
          <PlanCard
            name="Free"
            price="R$ 0"
            caption="para testar o fluxo"
            features={['3 palavras-chave', '10 alertas por dia', 'Painel essencial']}
            cta="Começar grátis"
            href={realLanding ? '/auth/register' : undefined}
            onClick={realLanding ? undefined : () => onNavigate('dashboard')}
          />
          <PlanCard
            name="Pro"
            price="R$ 47"
            caption="por mês"
            features={['Palavras-chave ilimitadas', 'Alertas ilimitados', 'Suporte via WhatsApp']}
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
          <h2>Organiza sinais. A decisão continua sendo sua.</h2>
          <p>O SmartPayBot ajuda a reduzir busca manual e manter oportunidades em um só lugar, sem prometer contratação ou resultado garantido.</p>
        </Card>
        <div className="spb-250k-proof-list">
          <span>Independente</span>
          <span>Objetivo</span>
          <span>Sem promessa exagerada</span>
        </div>
      </section>

      <section className="spb-final-cta spb-250k-final-cta">
        <SectionHeader title="Comece pelo essencial" copy="Teste o Free, conecte seu Telegram e evolua quando os limites começarem a atrapalhar." />
        <div className="spb-hero-actions">
          <Button href={realLanding ? '/auth/register' : undefined} onClick={realLanding ? undefined : () => onNavigate('dashboard')}>Começar grátis</Button>
          <Button variant="secondary" href={realLanding ? '/pro' : undefined} onClick={realLanding ? undefined : () => onNavigate('pro')}>Conhecer Pro</Button>
        </div>
      </section>
    </main>
  )
}