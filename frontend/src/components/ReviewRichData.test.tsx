import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { ReviewRichData } from './ReviewRichData'

it('renders translated known values, safe unknown fields, and hides broken images', () => {
  render(
    <ReviewRichData
      details={{ 'Meal Type': 'Dinner', food: 3, 'custom-detail': ['Quiet', 'Cozy'], recommended_dishes: 'A deliberately long recommendation that uses the full metadata row.' }}
      translatedDetails={{ meal_type: 'Cena', orphan: 'Ignored' }}
      images={[{ url: 'https://lh3.googleusercontent.com/photo', position: 0, provider: 'serpapi' }]}
    />
  )
  expect(screen.getByText('Meal type')).toBeInTheDocument()
  expect(screen.getByText('Cena')).toBeInTheDocument()
  expect(screen.getByText('Custom Detail')).toBeInTheDocument()
  expect(screen.getByText('Quiet, Cozy')).toBeInTheDocument()
  expect(screen.getByText('Recommended dishes')).toBeInTheDocument()
  expect(screen.queryByText('Ignored')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('3 out of 5 stars')).not.toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
  expect(screen.getByLabelText('Review details')).toHaveClass('lg:grid-cols-3')
  const image = screen.getByRole('img', { name: 'Review photo 1' })
  expect(image).toHaveAttribute('referrerpolicy', 'no-referrer')
  expect(screen.getByLabelText('Review photos')).toHaveClass('min-w-0')
  expect(screen.getByTestId('review-photo-strip')).toHaveClass('w-full', 'max-w-full', 'overflow-x-auto')
  fireEvent.error(image)
  expect(screen.queryByRole('img', { name: 'Review photo 1' })).not.toBeInTheDocument()
})
