import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export const useActiveFooterLink = (linksConfig) => {
  const location = useLocation();
  const [activeIndex, setActiveIndex] = useState(null);

  useEffect(() => {
    const currentPath = location.pathname;
    const foundIndex = linksConfig.findIndex(link => 
      currentPath === link.path || 
      (link.matchSubpaths && currentPath.startsWith(link.path))
    );
    
    setActiveIndex(foundIndex >= 0 ? foundIndex : null);
  }, [location.pathname, linksConfig]);

  const setActive = (index) => {
    setActiveIndex(index);
  };

  const isActive = (index) => {
    return activeIndex === index ? '_active' : '';
  };

  return { isActive, setActive, activeIndex };
};