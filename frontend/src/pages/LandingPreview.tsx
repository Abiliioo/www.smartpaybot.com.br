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
    <main className={`spb-preview-page ${realLanding ? 'spb-preview-page--landing' : 'spb-preview-page--preview'}`}>
      <section className="spb-hero-grid">
        <div className="spb-hero-copy">
          <p className="spb-kicker">Alertas de freelas direto no Telegram</p>
          <h1>Receba oportunidades relevantes sem garimpar projeto por projeto.</h1>
          <p>
            Configure suas palavras-chave, receba alertas no Telegram e abra só os projetos que fazem sentido para o seu trabalho.
          </p>
          <div className="spb-hero-actions">
            {realLanding ? (
              <>
                <Button href="/auth/register">Começar grátis</Button>
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
            <span>Exemplo de alerta</span>
            <strong>há 4 min</strong>
          </div>
          <h2>Automação de planilha para controle de estoque</h2>
          <dl>
            <div><dt>Keyword</dt><dd>Excel</dd></div>
            <div><dt>Propostas</dt><dd>3</dd></div>
            <div><dt>Cliente</dt><dd>4.8 / 5</dd></div>
          </dl>
          <Button variant="secondary" href={realLanding ? '/dashboard/' : undefined}>
            Ver no dashboard
          </Button>
        </Card>
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
        <SectionHeader title="Como funciona" copy="Você configura uma vez e acompanha os alertas direto pelo Telegram." />
        <div className="spb-step-grid">
          <StepCard step="01" title="Escolha suas keywords" copy="Cadastre termos como Excel, Python, automação, design ou o nicho que você atende." />
          <StepCard step="02" title="Conecte Telegram" copy="Vincule seu Telegram para receber os alertas no celular." />
          <StepCard step="03" title="Receba e decida rápido" copy="Veja o contexto do projeto e abra o dashboard quando quiser analisar melhor." />
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
    </main>
  )
}
