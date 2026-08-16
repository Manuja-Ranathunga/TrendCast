import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Explorer } from './pages/Explorer'
import { ChannelDetail } from './pages/ChannelDetail'
import { Forecast } from './pages/Forecast'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Explorer />} />
        <Route path="/channels/:channelId" element={<ChannelDetail />} />
        <Route path="/forecast" element={<Forecast />} />
      </Route>
    </Routes>
  )
}

export default App
