/**
 * Gerador igual ao `random.Random(seed).random()` do Python (Mersenne Twister), para o desempate por SORTEIO dar
 * exatamente o mesmo resultado no celular e no servidor.
 */
const N = 624
const M = 397

function initGenrand(s: number): Uint32Array {
  const mt = new Uint32Array(N)
  mt[0] = s >>> 0
  for (let i = 1; i < N; i++) {
    const prev = mt[i - 1] ^ (mt[i - 1] >>> 30)
    mt[i] = (Math.imul(1812433253, prev) + i) >>> 0
  }
  return mt
}

function initByArray(key: number[]): { mt: Uint32Array; index: number } {
  const mt = initGenrand(19650218)
  let i = 1
  let j = 0
  for (let k = Math.max(N, key.length); k > 0; k--) {
    const prev = mt[i - 1] ^ (mt[i - 1] >>> 30)
    mt[i] = ((mt[i] ^ Math.imul(prev, 1664525)) + key[j] + j) >>> 0
    i++
    j++
    if (i >= N) {
      mt[0] = mt[N - 1]
      i = 1
    }
    if (j >= key.length) j = 0
  }
  for (let k = N - 1; k > 0; k--) {
    const prev = mt[i - 1] ^ (mt[i - 1] >>> 30)
    mt[i] = ((mt[i] ^ Math.imul(prev, 1566083941)) - i) >>> 0
    i++
    if (i >= N) {
      mt[0] = mt[N - 1]
      i = 1
    }
  }
  mt[0] = 0x80000000
  return { mt, index: N }
}

export class PyRandom {
  private mt: Uint32Array
  private index: number

  /** `seed`: inteiro (como em `random.Random(seed)`); usa o valor absoluto, em pedaços de 32 bits. */
  constructor(seed: number) {
    let n = BigInt(Math.abs(Math.trunc(seed)))
    const key: number[] = []
    if (n === 0n) key.push(0)
    while (n > 0n) {
      key.push(Number(n & 0xffffffffn))
      n >>= 32n
    }
    const s = initByArray(key)
    this.mt = s.mt
    this.index = s.index
  }

  private genrand(): number {
    const mt = this.mt
    if (this.index >= N) {
      let kk = 0
      let y: number
      for (; kk < N - M; kk++) {
        y = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff)
        mt[kk] = mt[kk + M] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0)
      }
      for (; kk < N - 1; kk++) {
        y = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff)
        mt[kk] = mt[kk + (M - N)] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0)
      }
      y = (mt[N - 1] & 0x80000000) | (mt[0] & 0x7fffffff)
      mt[N - 1] = mt[M - 1] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0)
      this.index = 0
    }
    let y = mt[this.index++]
    y ^= y >>> 11
    y ^= (y << 7) & 0x9d2c5680
    y ^= (y << 15) & 0xefc60000
    y ^= y >>> 18
    return y >>> 0
  }

  /** Igual a `random.random()`: número em [0, 1) com 53 bits. */
  random(): number {
    const a = this.genrand() >>> 5
    const b = this.genrand() >>> 6
    return (a * 67108864 + b) / 9007199254740992
  }
}
