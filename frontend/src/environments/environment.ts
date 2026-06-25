export const environment = {
  apiBaseUrl: '/api',
  wsBaseUrl: `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/realtime/`,
};

