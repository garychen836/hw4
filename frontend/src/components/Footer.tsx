import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <h4>Campus Customs</h4>
          <p>Officially licensed Yale apparel, designed and printed for the Yale community.</p>
        </div>
        <div>
          <h4>Shop</h4>
          <Link to="/products">All products</Link>
          <Link to="/about">About us</Link>
        </div>
        <div>
          <h4>Account</h4>
          <Link to="/login">Log in</Link>
          <Link to="/signup">Create account</Link>
        </div>
        <div>
          <h4>Visit</h4>
          <p>
            57 Broadway
            <br />
            New Haven, CT 06511
          </p>
        </div>
      </div>
      <div className="container footer-bottom">
        © {new Date().getFullYear()} Campus Customs. A class project for MGT 409, not the official store.
      </div>
    </footer>
  )
}
