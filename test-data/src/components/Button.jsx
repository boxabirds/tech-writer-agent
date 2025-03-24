import React from 'react';

/**
 * A reusable button component
 * @param {Object} props - Component props
 * @param {string} props.text - Button text
 * @param {function} props.onClick - Click handler
 * @param {string} [props.variant='primary'] - Button variant
 * @returns {JSX.Element} Button component
 */
const Button = ({ text, onClick, variant = 'primary' }) => {
  return (
    <button 
      className={`button button--${variant}`}
      onClick={onClick}
    >
      {text}
    </button>
  );
};

export default Button;
