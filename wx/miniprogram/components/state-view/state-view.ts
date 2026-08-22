Component({
  properties: {
    state: { type: String, value: 'empty' },
    message: { type: String, value: '' },
    action: { type: String, value: '' },
    title: { type: String, value: '' },
    description: { type: String, value: '' },
    actionText: { type: String, value: '' },
  },
  methods: {
    onAction() {
      this.triggerEvent('action')
    },
  },
})
