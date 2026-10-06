import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { categoryOf, fetchProduct, formatPrice, type Product } from '../api'
import { setViewedProduct } from '../pageContext'

function stockLabel(qty: number) {
  if (qty === 0) return 'Sold out'
  if (qty <= 5) return `Only ${qty} left`
  return 'In stock'
}

// Amazon-style single product page: big photo on the left, details on the right.
export default function ProductDetail() {
  const { productId = '' } = useParams()
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [size, setSize] = useState<string | null>(null)

  useEffect(() => {
    setProduct(null)
    setError(null)
    setSize(null)
    fetchProduct(productId)
      .then((p) => {
        setProduct(p)
        const firstInStock = p.inventory?.find((s) => s.quantity > 0)
        setSize(firstInStock?.size ?? null)
      })
      .catch((e: Error) => setError(e.message === 'Not found' ? 'This product does not exist.' : 'Could not load this product.'))
  }, [productId])

  // Tell the chat which product (and size) the shopper is looking at.
  useEffect(() => {
    setViewedProduct(product?.product_id ?? productId, size)
    return () => setViewedProduct(null)
  }, [product, productId, size])

  if (error)
    return (
      <div className="container section">
        <p className="error">{error}</p>
        <Link to="/products">← Back to all products</Link>
      </div>
    )
  if (!product) return <div className="container section muted">Loading…</div>

  const selected = product.inventory?.find((s) => s.size === size)

  return (
    <div className="container section">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/">Home</Link> › <Link to="/products">Products</Link> › <span>{categoryOf(product)}</span>
      </nav>

      <div className="detail">
        <div className="detail-image">
          <img src={product.image_url} alt={product.name} />
        </div>

        <div className="detail-info">
          <h1>{product.name}</h1>
          <p className="detail-type">{product.garment_type}</p>
          <p className="detail-price">{formatPrice(product.price)}</p>

          <p className={`stock ${product.total_stock === 0 ? 'out' : 'in'}`}>
            {product.total_stock === 0 ? 'Currently sold out in all sizes' : 'In stock'}
          </p>

          <div className="detail-block">
            <p className="label">
              Size: <strong>{size ?? 'Select a size'}</strong>
            </p>
            <div className="size-grid">
              {product.inventory?.map((s) => (
                <button
                  key={s.size}
                  className={`size-btn ${size === s.size ? 'active' : ''}`}
                  disabled={s.quantity === 0}
                  onClick={() => setSize(s.size)}
                  title={stockLabel(s.quantity)}
                >
                  <span>{s.size}</span>
                  <small>{stockLabel(s.quantity)}</small>
                </button>
              ))}
            </div>
            {selected && selected.quantity > 0 && selected.quantity <= 5 && (
              <p className="low-stock">Hurry, only {selected.quantity} left in {selected.size}.</p>
            )}
          </div>

          <button className="btn btn-primary btn-block" disabled title="Checkout is not part of this demo">
            Add to bag (coming soon)
          </button>
          <button
            className="btn btn-secondary btn-block ask-item"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent('open-chat', {
                  detail: { ask: size ? `Tell me about this one. Is it in stock in ${size}?` : 'Tell me about this one.' },
                }),
              )
            }
          >
            💬 Ask about this item
          </button>

          <table className="spec-table">
            <tbody>
              <tr>
                <th>Type</th>
                <td>{product.garment_type}</td>
              </tr>
              <tr>
                <th>Colors</th>
                <td>{product.colors.length ? product.colors.join(', ') : 'See photo'}</td>
              </tr>
              <tr>
                <th>Category</th>
                <td>{categoryOf(product)}</td>
              </tr>
              <tr>
                <th>Item ID</th>
                <td className="mono">{product.product_id}</td>
              </tr>
            </tbody>
          </table>

          <div className="detail-block">
            <h2>About this item</h2>
            <p>{product.description}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
