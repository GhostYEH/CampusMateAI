import { repository } from './services/repository'

App<IAppOption>({
  globalData: {
    apiBaseUrl: '',
  },
  onLaunch() {
    repository.bootstrap()
  },
})
