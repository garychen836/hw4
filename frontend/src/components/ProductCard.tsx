import { Link } from 'react-router-dom'
import { formatPrice, type Product } from '../api'

export default function ProductCard({ product }: { product: Product }) {
  const soldOut = product.total_stock === 0
  return (
    <Link to={`/products/${product.product_id}`} className="product-card">
      <div className="product-card-img">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        {soldOut && <span className="badge badge-soldout">Sold out</span>}
      </div>
      <div className="product-card-body">
        <h3>{product.name}</h3>
        <p className="product-card-type">{product.garment_type}</p>
        <p className="product-card-desc">{product.description}</p>
        <p className="price">{formatPrice(product.price)}</p>
      </div>
    </Link>
  )
}
