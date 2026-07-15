import axios from 'axios'

const apiKey = import.meta.env.VITE_API_KEY

const api = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
    ...(apiKey ? { 'X-API-Key': apiKey } : {}),
  },
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message = err.response?.data?.detail || err.message || 'Unknown error'
    console.error('[API]', message)
    return Promise.reject(new Error(message))
  }
)

export default api
