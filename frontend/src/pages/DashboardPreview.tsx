import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { KeywordPill } from '../components/KeywordPill'
import { MetricCard } from '../components/MetricCard'
import { Pill } from '../components/Pill'
import { TelegramPanel } from '../components/TelegramPanel'
import { keywords, metrics, recentProjects } from '../api/mockData'
import type { PreviewView } from '../types'

type DashboardPreviewProps = {
  onNavigate: (view: PreviewView) => void
}

export function DashboardPreview({ onNavigate }: DashboardPreviewProps) {
  return (
    <main className="spb-preview-page spb-dashboard-preview">
      <section className="spb-dashboard-hero">
        <div>
          <Pill tone="green">Monitoramento ativo</Pill>
          <h1>Dashboard</h1>
          <p>Visao rapida do que esta chegando, do limite atual e do proximo melhor passo.</p>
        </div>
        <Button onClick={() => onNavigate('pro')}>Upgrade Pro</Button>
      </section>

      <section className="spb-metric-grid">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </section>

      <section className="spb-dashboard-grid">
        <Card className="spb-wide-card">
          <div className="spb-panel-title">
            <div>
              <span>Projetos recentes</span>
              <h3>Oportunidades para revisar agora</h3>
            </div>
            <Pill tone="blue">12 hoje</Pill>
          </div>
          <div className="spb-project-list">
            {recentProjects.map((project) => (
              <article key={project.title}>
                <div>
                  <h4>{project.title}</h4>
                  <p>{project.keyword} baseado nas suas keywords</p>
                </div>
                <span>{project.age}</span>
                <strong>{project.proposals} propostas</strong>
              </article>
            ))}
          </div>
        </Card>

        <TelegramPanel connected />

        <Card>
          <div className="spb-panel-title">
            <div>
              <span>Keywords</span>
              <h3>Monitoradas</h3>
            </div>
            <Pill tone="amber">5 / 3 Free</Pill>
          </div>
          <div className="spb-keyword-list">
            {keywords.map((keyword) => <KeywordPill key={keyword} label={keyword} />)}
          </div>
          <p className="spb-card-note">Duas keywords extras ficariam pausadas no plano Free.</p>
        </Card>

        <Card tone="accent" className="spb-upgrade-panel">
          <span>Plano atual</span>
          <h3>Free com limite proximo</h3>
          <p>Mostre o valor no contexto: quando o limite aparece, o upgrade vira uma decisao natural.</p>
          <Button onClick={() => onNavigate('pro')}>Liberar ilimitado</Button>
        </Card>

        <Card tone="quiet" className="spb-empty-useful">
          <h3>Sem ganhos marcados ainda</h3>
          <p>Quando voce marcar um projeto como ganho, receita, conversao e ticket medio aparecem aqui.</p>
        </Card>
      </section>
    </main>
  )
}
