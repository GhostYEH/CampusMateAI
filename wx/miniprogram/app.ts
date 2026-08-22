import { repository } from './services/repository'

App<IAppOption>({
  globalData: {
    apiBaseUrl: 'http://192.168.1.17:8000',
  },
  onLaunch() {
    repository.bootstrap()
  },
})
