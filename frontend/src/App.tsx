import { BrandMark } from './components/BrandMark'

function App() {
  return (
    <main className="spb-react-probe">
      <header className="spb-react-header">
        <BrandMark />
      </header>

      <section className="spb-react-panel" aria-labelledby="react-probe-title">
        <p className="spb-react-kicker">Same-origin React probe</p>
        <h1 id="react-probe-title">React UI foundation ready</h1>
        <p>
          Setup minimo de React, TypeScript e Vite preparado para o
          SmartPayBot. Flask continua responsavel por API, autenticacao,
          sessao e regras de negocio.
        </p>
      </section>
    </main>
  )
}

export default App
