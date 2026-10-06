import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CATEGORIES, COLLECTIONS, categoryOf, fetchProducts, formatPrice, type Product } from '../api'
import ProductCard from '../components/ProductCard'
import BulldogAvatar from '../components/BulldogAvatar'

// Hand-picked items for the hero collage and best sellers.
const HERO_IDS = ['champion-reverse-weave-hoodie-1', 'district-vit-hoodie-vintage-bulldog', 'yale-grandpa-crewneck']
const BEST_SELLER_IDS = [
  'basic-hoodie-big-yale',
  'yale-grandpa-crewneck',
  '2025-yale-vs-harvard-t-shirt',
  'benjamin-franklin-fleece-jacket',
]
const GAME_ID = '2025-yale-vs-harvard-t-shirt'
const TICKER = [
  'Lux et Veritas',
  'Boola Boola',
  'Bulldogs since 1701',
  'Residential college pride',
  'Go Bulldogs',
  'Officially licensed',
  'Sizes XS to XXL',
]

const pick = (all: Product[], ids: string[]) =>
  ids.map((id) => all.find((p) => p.product_id === id)).filter((p): p is Product => Boolean(p))

export default function Home() {
  const [products, setProducts] = useState<Product[]>([])

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setProducts([]))
  }, [])

  const byId = useMemo(() => new Map(products.map((p) => [p.product_id, p])), [products])
  const hero = pick(products, HERO_IDS)
  const bestSellers = pick(products, BEST_SELLER_IDS)
  const game = byId.get(GAME_ID)

  const categoryStats = useMemo(
    () =>
      CATEGORIES.map((c) => {
        const items = products.filter((p) => categoryOf(p) === c)
        return {
          name: c,
          count: items.length,
          from: items.length ? Math.min(...items.map((p) => p.price)) : 0,
          cover: items.find((p) => p.total_stock > 0) ?? items[0],
        }
      }),
    [products],
  )

  return (
    <>
      {/* ---------- Hero ---------- */}
      <section className="home-hero">
        <div className="home-hero-bg" aria-hidden="true">
          <span className="hero-watermark">Y</span>
        </div>
        <div className="container home-hero-inner">
          <div className="home-hero-copy">
            <p className="eyebrow">Officially licensed · New Haven, CT</p>
            <h1>
              Bright College <em>Years,</em>
              <br />
              worn well.
            </h1>
            <p className="hero-sub">
              Yale apparel for every chapter, from first-year move-in to your twenty-fifth reunion. Residential
              colleges, varsity teams, graduate schools, and the whole Yale family.
            </p>
            <div className="hero-actions">
              <Link to="/products" className="btn btn-light btn-lg">
                Shop the collection
              </Link>
              <button className="btn btn-outline-light btn-lg" onClick={() => window.dispatchEvent(new Event('open-chat'))}>
                Ask our assistant
              </button>
            </div>
            <dl className="hero-stats">
              <div>
                <dt>{products.length || '…'}</dt>
                <dd>styles</dd>
              </div>
              <div>
                <dt>{COLLECTIONS.length}</dt>
                <dd>collections</dd>
              </div>
              <div>
                <dt>XS–XXL</dt>
                <dd>every design</dd>
              </div>
            </dl>
          </div>

          <div className="hero-collage" aria-label="Featured products">
            {hero.map((p, i) => (
              <Link key={p.product_id} to={`/products/${p.product_id}`} className={`collage-card collage-${i}`}>
                <img src={p.image_url} alt={p.name} />
                <span className="collage-tag">
                  {p.name} <strong>{formatPrice(p.price)}</strong>
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Ticker ---------- */}
      <div className="ticker" aria-hidden="true">
        <div className="ticker-track">
          {[...TICKER, ...TICKER].map((t, i) => (
            <span key={i}>
              {t} <b>✦</b>
            </span>
          ))}
        </div>
      </div>

      {/* ---------- Shop by collection ---------- */}
      <section className="container section">
        <div className="section-head">
          <div>
            <p className="kicker">Find your corner of Yale</p>
            <h2>Shop by collection</h2>
          </div>
          <Link to="/products" className="link-arrow">
            Browse everything →
          </Link>
        </div>
        <div className="collection-grid">
          {COLLECTIONS.map((c, i) => {
            const cover = byId.get(c.cover)
            const count = products.filter(c.match).length
            return (
              <Link
                key={c.key}
                to={`/products?collection=${c.key}`}
                className={`collection-tile ${i === 0 ? 'collection-tile-lg' : ''}`}
              >
                {cover && <img src={cover.image_url} alt="" />}
                <div className="collection-tile-text">
                  <h3>{c.title}</h3>
                  <p>{c.blurb}</p>
                  <span className="collection-count">{count ? `${count} styles →` : 'Shop now →'}</span>
                </div>
              </Link>
            )
          })}
        </div>
      </section>

      {/* ---------- The Game feature ---------- */}
      {game && (
        <section className="game-banner">
          <div className="container game-inner">
            <div className="game-copy">
              <p className="kicker kicker-light">The Game · 2025</p>
              <h2>
                Yale <span className="vs">vs.</span> Harvard
              </h2>
              <p>
                One of college football's oldest rivalries deserves a shirt to match. Our 2025 edition features both
                helmets head to head, in soft heather gray.
              </p>
              <div className="game-price">
                <span>{formatPrice(game.price)}</span>
                <Link to={`/products/${game.product_id}`} className="btn btn-light">
                  Get game-day ready
                </Link>
              </div>
            </div>
            <Link to={`/products/${game.product_id}`} className="game-image">
              <img src={game.image_url} alt={game.name} />
            </Link>
          </div>
        </section>
      )}

      {/* ---------- Shop by category ---------- */}
      <section className="container section">
        <div className="section-head">
          <div>
            <p className="kicker">Something for every season</p>
            <h2>Shop by category</h2>
          </div>
        </div>
        <div className="category-row">
          {categoryStats.map((c) => (
            <Link key={c.name} to={`/products?category=${encodeURIComponent(c.name)}`} className="category-tile">
              <div className="category-img">{c.cover && <img src={c.cover.image_url} alt="" loading="lazy" />}</div>
              <h3>{c.name}</h3>
              <p>
                {c.count} styles · from {formatPrice(c.from)}
              </p>
            </Link>
          ))}
        </div>
      </section>

      {/* ---------- Best sellers ---------- */}
      <section className="section-alt">
        <div className="container">
          <div className="section-head">
            <div>
              <p className="kicker">Campus favorites</p>
              <h2>Best sellers</h2>
            </div>
            <Link to="/products" className="link-arrow">
              View all →
            </Link>
          </div>
          <div className="product-grid">
            {bestSellers.map((p) => (
              <ProductCard key={p.product_id} product={p} />
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Assistant callout ---------- */}
      <section className="container section">
        <div className="assistant-band">
          <div className="assistant-icon" aria-hidden="true">
            <BulldogAvatar size={58} />
          </div>
          <div>
            <h2>Not sure about size or color?</h2>
            <p>
              Our shopping assistant checks live prices and stock for every size, then shows you matching items right
              on the page.
            </p>
          </div>
          <button className="btn btn-primary btn-lg" onClick={() => window.dispatchEvent(new Event('open-chat'))}>
            Start a chat
          </button>
        </div>
      </section>

      {/* ---------- Promise strip ---------- */}
      <section className="promise-strip">
        <div className="container value-grid">
          <div>
            <span className="promise-icon">✓</span>
            <h3>Officially licensed</h3>
            <p>Every design is approved by Yale, so your gear is the real thing.</p>
          </div>
          <div>
            <span className="promise-icon">⌂</span>
            <h3>Made for the community</h3>
            <p>Colleges, teams, schools, and families, all in one place.</p>
          </div>
          <div>
            <span className="promise-icon">≡</span>
            <h3>Honest stock</h3>
            <p>What you see is what we have, straight from our inventory.</p>
          </div>
        </div>
      </section>
    </>
  )
}
