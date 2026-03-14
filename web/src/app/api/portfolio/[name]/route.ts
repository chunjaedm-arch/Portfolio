import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params
  const body = await req.json()
  try {
    const res = await fetch(`${BACKEND_URL}/api/portfolio/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) return NextResponse.json({ error: 'Backend error' }, { status: 502 })
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 503 })
  }
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params
  try {
    const res = await fetch(`${BACKEND_URL}/api/portfolio/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    })
    if (!res.ok) return NextResponse.json({ error: 'Backend error' }, { status: 502 })
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 503 })
  }
}
