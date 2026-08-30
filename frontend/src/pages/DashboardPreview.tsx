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
          <h1>Painel de oportunidades</h1>
          <p>Visão rápida do que chegou, dos limites do plano e do próximo passo mais útil.</p>
        </div>
        <Button onClick={() => onNavigate('pro')}>Conhecer Pro</Button>
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
              <span>Últimas oportunidades</span>
              <h3>Projetos para revisar agora</h3>
            </div>
            <Pill tone="blue">Atualizado automaticamente</Pill>
          </div>
          <div className="spb-project-list">
            {recentProjects.map((project) => (
              <article key={project.title}>
                <div>
                  <h4>{project.title}</h4>
                  <p>{project.keyword} entre as palavras-chave monitoradas</p>
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
              <span>Palavras-chave monitoradas</span>
              <h3>Termos em acompanhamento</h3>
            </div>
            <Pill tone="amber">5 / 3 Free</Pill>
          </div>
          <div className="spb-keyword-list">
            {keywords.map((keyword) => <KeywordPill key={keyword} label={keyword} />)}
          </div>
          <p className="spb-card-note">Duas palavras-chave extras ficariam pausadas no plano Free.</p>
        </Card>

        <Card tone="accent" className="spb-upgrade-panel">
          <span>Plano atual</span>
          <h3>Free perto do limite</h3>
          <p>Quando os alertas acabam cedo, o Pro amplia a cobertura sem mudar sua rotina.</p>
          <Button onClick={() => onNavigate('pro')}>Ver Pro</Button>
        </Card>

        <Card tone="quiet" className="spb-empty-useful">
          <h3>Revisão em andamento</h3>
          <p>Use o painel para acompanhar alertas recebidos e separar as oportunidades que merecem proposta.</p>
        </Card>
      </section>
    </main>
  )
}
