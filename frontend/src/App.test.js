import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App';

// Mock axios avant d'importer App
jest.mock('axios', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

import axios from 'axios';

describe('Logique de filtrage du composant App', () => {
  
  beforeEach(() => {
    // on reset axios
    // et on simule un backend qui renvoie un tableau vide
    axios.get.mockClear();
    axios.get.mockResolvedValue({ data: [] });
  });

  test('envoie le paramètre status="active" au clic sur le filtre Active', async () => {
    render(<App />);

    // On attend que le premier fetch initial du useEffect soit passé
    // React 18 en strict mode appelle les effets 2 fois au démarrage
    await waitFor(() => expect(axios.get).toHaveBeenCalled());
    const callsBefore = axios.get.mock.calls.length;

    // Act : On trouve le bouton "Active" et on clique dessus
    const activeBtn = screen.getByText('Active');
    fireEvent.click(activeBtn);

    // Assert : On vérifie que le nouvel appel contient les bons paramètres
    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/tasks', {
        params: { status: 'active' }
      });
    });
  });

  test('envoie UNIQUEMENT la date au clic sur le filtre Today (évite le bug du status)', async () => {
    render(<App />);
    
    await waitFor(() => expect(axios.get).toHaveBeenCalled());

    // Act : on clique sur le filtre "Today"
    const todayBtn = screen.getByText('Today');
    fireEvent.click(todayBtn);

    // On calcule la date du jour attendue par votre code
    const todayDate = new Date().toISOString().split('T')[0];

    // Assert : On vérifie l'absence du paramètre "status"
    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/tasks', {
        params: { today: todayDate } 
      });
    });
  });

});