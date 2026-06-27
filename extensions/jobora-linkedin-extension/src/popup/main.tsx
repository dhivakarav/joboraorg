import React from 'react';
import ReactDOM from 'react-dom/client';
import Popup from './Popup';
import '../sidebar/sidebar.css';  // shared Tailwind tokens

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Popup />
  </React.StrictMode>,
);
