import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import TaskList from './components/TaskList';
import TaskForm from './components/TaskForm';
import SearchBar from './components/SearchBar';
import Stats from './components/Stats';
import './App.css';

const API_URL = 'http://localhost:8000/api';

function App() {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);

  const fetchTasks = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      
      if (filter === 'today') {
        params.today = new Date().toISOString().split('T')[0];
      } else if (filter !== 'all') {
        params.status = filter;
      }

      const res = await axios.get(`${API_URL}/tasks`, { params });
      setTasks(res.data);
    } catch (err) {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { 
    fetchTasks(); 
  }, [fetchTasks]);

  const addTask = async (task) => {
    try {
      await axios.post(`${API_URL}/tasks`, task);
      fetchTasks();
    } catch (err) {
      // Error handled silently
    }
  };

  const toggleTask = async (id, isActive) => {
    try {
      await axios.put(`${API_URL}/tasks/${id}`, { is_active: !isActive });
      fetchTasks();
    } catch (err) {
      // Error handled silently
    }
  };

  const deleteTask = async (id) => {
    try {
      await axios.delete(`${API_URL}/tasks/${id}`);
      fetchTasks();
    } catch (err) {
      // Error handled silently
    }
  };

  const searchTasks = async (query) => {
    if (!query.trim()) {
      fetchTasks();
      return;
    }
    try {
      const res = await axios.get(`${API_URL}/search`, { params: { q: query } });
      setTasks(res.data);
    } catch (err) {
      // Error handled silently
    }
  };

  return (
    <div className="app">
      <header><h1>📋 Task Manager</h1><Stats apiUrl={API_URL} /></header>
      <main>
        <SearchBar onSearch={searchTasks} />
        <div className="filters">
          {['all', 'active', 'done', 'today'].map(f => (
            <button key={f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        <TaskForm onSubmit={addTask} />
        {loading ? <p className="loading">Loading...</p> : <TaskList tasks={tasks} onToggle={toggleTask} onDelete={deleteTask} />}
      </main>
    </div>
  );
}
export default App;
