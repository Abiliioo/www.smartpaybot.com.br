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
    <main className={`spb-preview-page ${realLanding ? 'spb-preview-page--landing' : 'spb-preview-page--preview'}`}>
      <section className="spb-hero-grid spb-landing-hero">
        <div className="spb-hero-copy">
          <p className="spb-kicker">Alertas de freelas direto no Telegram</p>
          <h1>Alertas de freelas direto no Telegram, sem garimpo manual.</h1>
          <p>
            Configure palavras-chave, receba oportunidades relevantes e decida pelo dashboard quando fizer sentido.
          </p>
          <div className="spb-hero-actions">
            {realLanding ? (
              <>
                <Button href="/auth/register">Começar grátis</Button>
                <Button variant="secondary" href="/pro">Conhecer Pro</Button>
              </>
            ) : (
              <>
                <Button onClick={() => onNavigate('dashboard')}>Ver dashboard</Button>
                <Button variant="secondary" onClick={() => onNavigate('pro')}>Conhecer Pro</Button>
              </>
            )}
          </div>
          <div className="spb-trust-strip" aria-label="Garantias do produto">
            <span>Produto independente</span>
            <span>Sem promessa de contratação</span>
            <span>Alertas por palavras-chave</span>
          </div>
        </div>

        <div className="spb-live-board" aria-label="Fluxo visual do SmartPayBot">
          <Card className="spb-alert-preview spb-live-board__alert">
            <div className="spb-alert-preview__top">
              <span>Telegram conectado</span>
              <strong>há 4 min</strong>
            </div>
            <h2>Automação de planilha para controle de estoque</h2>
            <dl>
              <div><dt>Keyword</dt><dd>Excel</dd></div>
              <div><dt>Propostas</dt><dd>3</dd></div>
              <div><dt>Status</dt><dd>Novo alerta</dd></div>
            </dl>
            <Button variant="secondary" href={realLanding ? '/dashboard/' : undefined}>
              Ver no dashboard
            </Button>
          </Card>

          <Card tone="quiet" className="spb-live-board__keyword">
            <span className="spb-mini-label">Keyword monitorada</span>
            <strong>Excel</strong>
            <p>Projeto filtrado antes de virar ruído na sua lista.</p>
          </Card>

          <Card tone="quiet" className="spb-live-board__limit">
            <span className="spb-mini-label">Plano atual</span>
            <strong>Free</strong>
            <p>3 keywords e 10 alertas por dia. Pro libera operação sem limite.</p>
          </Card>

          <Card tone="accent" className="spb-live-board__signal">
            <span className="spb-mini-label">Dashboard</span>
            <strong>Decisão rápida</strong>
            <p>Abra só as oportunidades que combinam com seu foco.</p>
          </Card>
        </div>
      </section>

      <section>
        <SectionHeader
          eyebrow="Por que existe"
          title="Menos garimpo manual, mais tempo para propor."
          copy="Pare de revisar listas manualmente e receba só oportunidades ligadas às palavras-chave que você escolher."
        />
        <div className="spb-three-grid">
          {[
            {
              title: 'Menos busca repetitiva',
              copy: 'O bot monitora novas oportunidades e destaca projetos ligados às suas keywords.',
            },
            {
              title: 'Mais velocidade para decidir',
              copy: 'Você recebe o alerta com contexto suficiente para avaliar se vale abrir o projeto.',
            },
            {
              title: 'Filtro mais claro',
              copy: 'Use termos do seu trabalho para reduzir ruído e focar nos projetos mais compatíveis.',
            },
          ].map((item) => (
            <Card key={item.title} tone="quiet">
              <h3>{item.title}</h3>
              <p>{item.copy}</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <SectionHeader title="Do termo monitorado à decisão" copy="Um fluxo simples para reduzir garimpo sem prometer resultado garantido." />
        <div className="spb-flow-grid">
          {[
            ['01', 'Keyword', 'Você cadastra termos ligados ao seu trabalho.'],
            ['02', 'Alerta', 'O Telegram avisa quando uma oportunidade combina.'],
            ['03', 'Dashboard', 'Você organiza e revisa os projetos recebidos.'],
            ['04', 'Decisão', 'Abra a proposta quando fizer sentido para sua rotina.'],
          ].map(([step, title, copy]) => (
            <Card key={step} tone="quiet" className="spb-flow-card">
              <span>{step}</span>
              <h3>{title}</h3>
              <p>{copy}</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <SectionHeader title="Planos" copy="Comece testando com limites. Faça upgrade quando quiser monitorar mais termos e receber mais alertas." />
        <div className="spb-plan-grid">
          <PlanCard
            name="Free"
            price="R$ 0"
            caption="para começar"
            features={['3 keywords', '10 alertas por dia', 'Dashboard essencial']}
            cta="Começar grátis"
            href={realLanding ? '/auth/register' : undefined}
          />
          <PlanCard
            name="Pro"
            price="R$ 47"
            caption="por mês"
            features={['Keywords ilimitadas', 'Alertas ilimitados', 'Mais flexibilidade para operar']}
            cta="Ver upgrade"
            featured
            href={realLanding ? '/pro' : undefined}
            onClick={realLanding ? undefined : () => onNavigate('pro')}
          />
        </div>
      </section>

      <section>
        <SectionHeader title="Credibilidade sem promessa vazia" copy="O SmartPayBot organiza sinais. A decisão e a proposta continuam sendo suas." />
        <div className="spb-proof-grid">
          <Card tone="quiet"><h3>Independente</h3><p>Produto sem vínculo oficial com plataformas de freelance.</p></Card>
          <Card tone="quiet"><h3>Recorrente</h3><p>Criado para freelancers que acompanham oportunidades todos os dias.</p></Card>
          <Card tone="quiet"><h3>Objetivo</h3><p>Alertas por palavras-chave, sem garantia de contratação ou posição na fila.</p></Card>
        </div>
      </section>

      <section className="spb-final-cta">
        <SectionHeader title="Comece pelo essencial" copy="Teste o Free, conecte seu Telegram e evolua para o Pro quando os limites começarem a pesar." />
        <div className="spb-hero-actions">
          <Button href={realLanding ? '/auth/register' : undefined} onClick={realLanding ? undefined : () => onNavigate('dashboard')}>Começar grátis</Button>
          <Button variant="secondary" href={realLanding ? '/pro' : undefined} onClick={realLanding ? undefined : () => onNavigate('pro')}>Conhecer Pro</Button>
        </div>
      </section>
    </main>
  )
}
