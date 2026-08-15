import { repository } from './services/repository'

App<IAppOption>({
  globalData: {
    apiBaseUrl: 'http://192.168.1.14:8000',
  },
  onLaunch() {
    repository.bootstrap()
  },
})
