import { type AnchorHTMLAttributes, type PropsWithChildren } from 'react';
import { Link as RouterLink } from 'react-router-dom';

type LinkProps = PropsWithChildren<
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> & {
    href: string;
    replace?: boolean;
    prefetch?: boolean;
    scroll?: boolean;
  }
>;

export default function Link({ href, replace, children, ...props }: LinkProps) {
  const { prefetch: _prefetch, scroll: _scroll, ...linkProps } = props;

  return (
    <RouterLink to={href} replace={replace} {...linkProps}>
      {children}
    </RouterLink>
  );
}
