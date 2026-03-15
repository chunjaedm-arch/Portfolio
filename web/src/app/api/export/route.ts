import { NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'
const BACKEND_HEADERS = { 'X-API-Key': process.env.API_SECRET_KEY ?? '' }

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/export`, {
      cache: 'no-store',
      headers: BACKEND_HEADERS,
    })
    if (!res.ok) return NextResponse.json({ error: 'Backend error' }, { status: 502 })
    const blob = await res.blob()
    const disposition = res.headers.get('content-disposition') ?? 'attachment; filename=export.zip'
    return new NextResponse(blob, {
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': disposition,
      },
    })
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 503 })
  }
}
