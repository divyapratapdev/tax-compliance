package com.taxpilot.gateway.security;

import com.taxpilot.gateway.entity.CAFirm;
import com.taxpilot.gateway.repository.CAFirmRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.*;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class UserDetailsServiceImpl implements UserDetailsService {

    private final CAFirmRepository caFirmRepository;

    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        CAFirm firm = caFirmRepository.findByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException("CA firm not found: " + email));

        return new org.springframework.security.core.userdetails.User(
                firm.getEmail(),
                firm.getPasswordHash(),
                firm.getIsActive(),
                true, true, true,
                List.of(new SimpleGrantedAuthority("ROLE_CA_FIRM"))
        );
    }
}
