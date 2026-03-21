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

  // 항상 bcrypt.compare 실행 (username 분기로 타이밍 추론 방지)
  const isPasswordValid = await bcrypt.compare(password, validPassHash)
  const isUsernameValid = username === validUser

  if (!isUsernameValid || !isPasswordValid) {
    return NextResponse.json({ error: '아이디 또는 비밀번호가 틀렸습니다.' }, { status: 401 })
  }

  const res = NextResponse.json({ ok: true })
  res.cookies.set('portfolio_auth', secret, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
    maxAge: 60 * 60 * 24 * 30, // 30일
  })
  return res
}
