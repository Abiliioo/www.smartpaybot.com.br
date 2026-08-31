import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { KeywordPill } from '../components/KeywordPill'
import { MetricCard } from '../components/MetricCard'
import { Pill } from '../components/Pill'
import { TelegramPanel } from '../components/TelegramPanel'
import { activeKeywords, opportunities, pausedKeywords, statusMetrics } from '../api/mockData'
import type { PreviewView } from '../types'

type DashboardPreviewProps = {
  onNavigate: (view: PreviewView) => void
}

export function DashboardPreview({ onNavigate }: DashboardPreviewProps) {
  return (
    <main className="spb-preview-page spb-dashboard-preview spb-dashboard-preview--premium">
      <section className="spb-dashboard-command">
        <div>
          <p className="spb-kicker">Painel de oportunidades</p>
          <h1>Seu monitoramento está ativo.</h1>
          <p>Revise os alertas mais recentes, acompanhe o limite do Free e escolha onde vale abrir proposta.</p>
        </div>
        <div className="spb-dashboard-command__status" aria-label="Resumo do monitoramento">
          <span><strong>Monitoramento</strong><small>Ativo</small></span>
          <span><strong>Telegram</strong><small>Conectado</small></span>
          <span><strong>Plano</strong><small>Free</small></span>
          <Button onClick={() => onNavigate('pro')}>Remover limite</Button>
        </div>
      </section>

      <section className="spb-metric-grid spb-dashboard-status-grid">
        {statusMetrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </section>

      <section className="spb-dashboard-workspace">
        <Card className="spb-opportunity-board">
          <div className="spb-panel-title">
            <div>
              <span>Últimas oportunidades</span>
              <h3>Para revisar agora</h3>
            </div>
            <Pill tone="blue">4 abertas</Pill>
          </div>
          <div className="spb-opportunity-list">
            {opportunities.map((project) => (
              <article key={project.title} className="spb-opportunity-item">
                <div className="spb-opportunity-item__main">
                  <div>
                    <h4>{project.title}</h4>
                    <p>{project.summary}</p>
                  </div>
                  <div className="spb-opportunity-tags">
                    <span>{project.keyword}</span>
                    <span>{project.age}</span>
                    <span>{project.proposals} propostas</span>
                    <strong>{project.priority}</strong>
                  </div>
                </div>
                <div className="spb-opportunity-actions" aria-label={`Ações para ${project.title}`}>
                  <Button variant="secondary">Abrir</Button>
                  <Button variant="ghost">Salvar</Button>
                  <Button variant="ghost">Ignorar</Button>
                </div>
              </article>
            ))}
          </div>
        </Card>

        <aside className="spb-dashboard-sidebar" aria-label="Resumo operacional">
          <Card className="spb-limit-card">
            <div className="spb-panel-title">
              <div>
                <span>Limite Free</span>
                <h3>8/10 alertas usados hoje</h3>
              </div>
              <Pill tone="amber">Perto do limite</Pill>
            </div>
            <div className="spb-limit-bar" aria-label="8 de 10 alertas usados"><span style={{ width: '80%' }} /></div>
            <p>Faltam 2 alertas antes de pausar por hoje.</p>
            <Button onClick={() => onNavigate('pro')}>Remover limite com Pro</Button>
          </Card>

          <TelegramPanel connected />

          <Card className="spb-keyword-panel">
            <div className="spb-panel-title">
              <div>
                <span>Palavras-chave monitoradas</span>
                <h3>3 ativas no Free</h3>
              </div>
              <Pill tone="green">Ativo</Pill>
            </div>
            <div className="spb-keyword-list">
              {activeKeywords.map((keyword) => <KeywordPill key={keyword} label={keyword} />)}
            </div>
            <p className="spb-card-note">Pausadas no Free: {pausedKeywords.join(', ')}.</p>
            <Button variant="secondary" onClick={() => onNavigate('pro')}>Liberar palavras-chave</Button>
          </Card>

          <Card tone="quiet" className="spb-next-action-card">
            <span>Próxima melhor ação</span>
            <h3>Priorize os alertas de alta aderência.</h3>
            <p>Revise os 4 alertas mais recentes antes de abrir novos projetos.</p>
          </Card>
        </aside>
      </section>
    </main>
  )
}