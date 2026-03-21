import { NextRequest, NextResponse } from 'next/server'

// Timing-safe string comparison
async function timingSafeEqual(a: string, b: string): Promise<boolean> {
  // This function is designed to run in constant time to mitigate timing attacks.
  // It's important that we don't exit early based on string length differences.
  if (typeof a !== 'string' || typeof b !== 'string') {
    return false;
  }

  const encoder = new TextEncoder();
  
  // We hash both strings with a cryptographic hash function.
  // The digestion process itself is not guaranteed to be constant time,
  // but it's a much better approach than direct byte-by-byte comparison
  // in a language where we can't control low-level optimizations.
  // The key property is that the resulting hashes will have a fixed length.
  const hashA = await crypto.subtle.digest('SHA-256', encoder.encode(a));
  const hashB = await crypto.subtle.digest('SHA-256', encoder.encode(b));

  const viewA = new Uint8Array(hashA);
  const viewB = new Uint8Array(hashB);

  // The length of the hashes should always be the same (32 bytes for SHA-256).
  // We check it just in case, but this branch should not be taken.
  if (viewA.length !== viewB.length) {
    return false;
  }
  
  // Compare the two hashes in a way that doesn't short-circuit.
  // We use a bitwise OR to accumulate differences.
  let mismatch = 0;
  for (let i = 0; i < viewA.length; i++) {
    mismatch |= viewA[i] ^ viewB[i];
  }

  // `mismatch` will be 0 if and only if the two hashes are identical.
  return mismatch === 0;
}


export async function proxy(req: NextRequest) {
  const token = req.cookies.get('portfolio_auth')?.value ?? ''
  const secret = process.env.AUTH_SECRET ?? ''

  // Authenticate by comparing the cookie with the secret in a timing-safe way.
  const authed = secret ? await timingSafeEqual(token, secret) : false

  if (!authed) {
    const loginUrl = new URL('/login', req.url)
    return NextResponse.redirect(loginUrl)
  }
  
  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!login|api/auth|_next/static|_next/image|favicon.ico).*)'],
}
