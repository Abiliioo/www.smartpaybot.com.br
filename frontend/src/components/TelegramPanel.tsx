import { Button } from './Button'
import { Card } from './Card'
import { Pill } from './Pill'

type TelegramPanelProps = {
  connected?: boolean
}

export function TelegramPanel({ connected = true }: TelegramPanelProps) {
  return (
    <Card className="spb-telegram-panel">
      <div className="spb-panel-title">
        <div>
          <span>Telegram</span>
          <h3>{connected ? 'Conectado e recebendo' : 'Conecte em 2 passos'}</h3>
        </div>
        <Pill tone={connected ? 'green' : 'amber'}>{connected ? 'Ativo' : 'Pendente'}</Pill>
      </div>
      <p>
        {connected
          ? 'Alertas chegam no celular quando uma oportunidade combina com suas palavras-chave.'
          : 'Abra o bot, envie seu código de conexão e volte para ativar o monitoramento.'}
      </p>
      <div className="spb-telegram-actions">
        <Button variant={connected ? 'secondary' : 'primary'}>{connected ? 'Ver status' : 'Abrir bot'}</Button>
        <Button variant="ghost">Gerar código</Button>
      </div>
    </Card>
  )
}