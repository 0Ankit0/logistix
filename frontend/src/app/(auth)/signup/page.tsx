'use client';

import { useEffect, useState } from 'react';
import { SignupForm } from '@/components/auth/signup-form';
import { getEnabledProviders, type OAuthProvider } from '@/lib/oauth';

export default function SignupPage() {
  const [enabledProviders, setEnabledProviders] = useState<OAuthProvider[]>([]);

  useEffect(() => {
    let active = true;

    getEnabledProviders().then((providers) => {
      if (active) {
        setEnabledProviders(providers);
      }
    });

    return () => {
      active = false;
    };
  }, []);

  return <SignupForm enabledProviders={enabledProviders} />;
}
