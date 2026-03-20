import { NextRequest, NextResponse } from 'next/server'
import bcrypt from 'bcrypt'

export async function POST(req: NextRequest) {
  const { username, password } = await req.json()

  const validUser = process.env.AUTH_USERNAME ?? ''
  const validPassHash = process.env.AUTH_PASSWORD ?? ''
  const secret = process.env.AUTH_SECRET ?? ''

  if (!validUser || !validPassHash || !secret) {
    return NextResponse.json({ error: '서버 설정 오류' }, { status: 500 })
  }

  // Compare the provided password with the stored hash
  const isPasswordValid = await bcrypt.compare(password, validPassHash)

  if (username !== validUser || !isPasswordValid) {
    return NextResponse.json({ error: '아이디 또는 비밀번호가 틀렸습니다.' }, { status: 401 })
  }

  const res = NextResponse.json({ ok: true })
  res.cookies.set('portfolio_auth', secret, {
    httpOnly: true,
    sameSite: 'strict',
    path: '/',
    maxAge: 60 * 60 * 24 * 30, // 30일
  })
  return res
}
