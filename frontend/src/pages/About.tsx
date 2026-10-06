import { Link } from 'react-router-dom'

export default function About() {
  return (
    <>
      <section className="hero hero-slim">
        <div className="container hero-inner">
          <p className="eyebrow">About us</p>
          <h1>Built for the Yale community.</h1>
        </div>
      </section>

      <div className="container section prose">
        <h2>Who we are</h2>
        <p>
          Campus Customs is an officially licensed retailer of Yale apparel based at 57 Broadway in New Haven. We
          design, print, and sell clothing that lets students, alumni, faculty, and families show their connection to
          Yale, from the first day of orientation to every reunion after.
        </p>

        <h2>What we offer</h2>
        <p>
          Our collection covers the full Yale experience: residential college crewnecks, varsity and club sports
          hoodies, graduate and professional school quarter-zips, family designs for proud parents and grandparents,
          and classic Yale and Bulldog favorites. Each product is available in sizes XS through XXL.
        </p>

        <h2>Our commitments</h2>
        <ul>
          <li>
            <strong>Authentic.</strong> Every design is officially licensed by Yale University.
          </li>
          <li>
            <strong>Honest.</strong> The prices and stock you see on this site come straight from our inventory, so
            what we show is what we have.
          </li>
          <li>
            <strong>Helpful.</strong> Our online shopping assistant can answer questions about products, sizes, and
            availability at any time.
          </li>
        </ul>

        <h2>Visit or contact us</h2>
        <p>
          Stop by our store at 57 Broadway, New Haven, CT 06511, or start a chat using the button in the bottom
          right corner.
        </p>

        <Link to="/products" className="btn btn-primary">
          Browse the collection
        </Link>
      </div>
    </>
  )
}
