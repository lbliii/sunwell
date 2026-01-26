/**
 * Redirect handler for legacy /preview?path=... URLs
 */

import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url, fetch }) => {
  const pathParam = url.searchParams.get('path');
  
  if (pathParam) {
    try {
      const response = await fetch('/api/project/slug', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: pathParam }),
      });
      
      if (response.ok) {
        const data = await response.json();
        const projectId = data.slug || data.projectId;
        
        if (projectId) {
          redirect(301, `/project/${projectId}/preview`);
        }
      }
    } catch {
      redirect(302, '/');
    }
    
    redirect(302, '/');
  }
  
  redirect(302, '/');
};
