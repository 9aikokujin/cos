import "./Loader.css";

const GlobalLoader = () => {
  return (
    <div className={`global-loader-overlay active`}>
      <div className="global-loader-content">
        <div className="global-loader-spinner"></div>
      </div>
    </div>
  );
};

export default GlobalLoader;
