'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    setLoading(false)
    if (res.ok) {
      router.push('/')
      router.refresh()
    } else {
      const data = await res.json()
      setError(data.error ?? '로그인 실패')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#1e1e2e]">
      <form
        onSubmit={handleSubmit}
        className="bg-[#2a2a3e] p-8 rounded-xl w-80 flex flex-col gap-4 shadow-xl"
      >
        <h1 className="text-white text-xl font-bold text-center">자산 관리 시스템</h1>
        <input
          type="text"
          placeholder="아이디"
          value={username}
          onChange={e => setUsername(e.target.value)}
          className="bg-[#1e1e2e] text-white px-4 py-2 rounded-lg outline-none border border-[#3a3a5e] focus:border-blue-500"
          autoComplete="username"
        />
        <input
          type="password"
          placeholder="비밀번호"
          value={password}
          onChange={e => setPassword(e.target.value)}
          className="bg-[#1e1e2e] text-white px-4 py-2 rounded-lg outline-none border border-[#3a3a5e] focus:border-blue-500"
          autoComplete="current-password"
        />
        {error && <p className="text-red-400 text-sm text-center">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg font-semibold transition-colors"
        >
          {loading ? '로그인 중...' : '로그인'}
        </button>
      </form>
    </div>
  )
}
