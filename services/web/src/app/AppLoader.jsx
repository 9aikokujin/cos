import './AppLoader.css';

const AppLoader = () => {
  return (
    <div className="app-loader">
      <div className="app-loader__content">
        <div className="app-loader__spinner"></div>
        <div className="app-loader__text">Загрузка приложения...</div>
      </div>
    </div>
  );
};

export default AppLoader;