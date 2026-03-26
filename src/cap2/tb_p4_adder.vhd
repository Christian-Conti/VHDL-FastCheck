library IEEE;
use IEEE.std_logic_1164.all;
use ieee.std_logic_unsigned.all;
use ieee.math_real.all; -- Required for uniform pseudo-random number generation

entity TB_P4_ADDER is
generic( NBIT_TEST		: integer := 32;
	 TEST_ITERATION		: integer := 10000;
	 SIM_TIME		: time := 1 ns );
end TB_P4_ADDER;

architecture TEST of TB_P4_ADDER is
    
    -- DUT component declaration
    component P4_ADDER is
        generic (
            NBIT :        integer);
        port (
            A :        in    std_logic_vector(NBIT-1 downto 0);
            B :        in    std_logic_vector(NBIT-1 downto 0);
            Cin :    in    std_logic;
            S :        out    std_logic_vector(NBIT-1 downto 0);
            Cout :    out    std_logic);
    end component;
    
    -- TB signals
    signal A_tb         : std_logic_vector(NBIT_TEST-1 downto 0);
    signal B_tb         : std_logic_vector(NBIT_TEST-1 downto 0);
    signal Cin_tb       : std_logic;
    signal S_tb         : std_logic_vector(NBIT_TEST-1 downto 0);
    signal Cout_tb      : std_logic;
    
    -- Signals for validation
    signal expected_sum : std_logic_vector(NBIT_TEST downto 0);
    signal cin_ext      : std_logic_vector(NBIT_TEST downto 0);
    
begin
    
	-- DUT instantiation
    DUT: P4_ADDER
        generic map (
            NBIT => NBIT_TEST
        )
        port map (
            A    => A_tb,
            B    => B_tb,
            Cin  => Cin_tb,
            S    => S_tb,
            Cout => Cout_tb
        );

    -- Golden result
    cin_ext <= (0 => Cin_tb, others => '0');  					-- Puts carry bit as LSB of an array NBIT_TEST
    expected_sum <= ('0' & A_tb) + ('0' & B_tb) + cin_ext;		

    -- Stimulus and validation process
    STIMULUS_PROC: process
        
		-- Variables for pseudo-random number generation
        variable seed1, seed2 : positive := 1;
        variable rand_val     : real;
        
        -- Validation counters
        variable errors       : integer := 0;
        variable tests_run    : integer := 0;
        
        -- Generate an N-bit random std_logic_vector
        impure function rand_slv(len : integer) return std_logic_vector is
            variable slv : std_logic_vector(len-1 downto 0);
        begin
            for i in 0 to len-1 loop
                uniform(seed1, seed2, rand_val);
                if rand_val > 0.5 then	-- Select between bit '0'/'1'
                    slv(i) := '1';
                else
                    slv(i) := '0';
                end if;
            end loop;
            return slv;
        end function;

    begin
        report "[TB] DUT Verification...";

        -- Test corner cases
        report "[TB] Testing: All Zeros arrays...";
        A_tb <= (others => '0'); 
        B_tb <= (others => '0'); 
        Cin_tb <= '0';

        wait for SIM_TIME;
        
		if (S_tb /= expected_sum(NBIT_TEST-1 downto 0)) or (Cout_tb /= expected_sum(NBIT_TEST)) then
            report "[ERROR] Test on all zeros failed!" severity error;
            errors := errors + 1;
        end if;
        
        report "[TB] Testing: All Ones arrays...";
        A_tb <= (others => '1'); 
        B_tb <= (others => '1'); 
        Cin_tb <= '1';
        
		wait for SIM_TIME;
        
		if (S_tb /= expected_sum(NBIT_TEST-1 downto 0)) or (Cout_tb /= expected_sum(NBIT_TEST)) then
            report "[ERROR] Test on all ones failed!" severity error;
            errors := errors + 1;
        end if;

        -- Test randomized inputs
        report "[TB] Testing: random test vectors...";
        for i in 1 to TEST_ITERATION loop
            -- Assign random vectors
            A_tb <= rand_slv(NBIT_TEST);
            B_tb <= rand_slv(NBIT_TEST);
            
            -- Randomize Cin
            uniform(seed1, seed2, rand_val);
            if rand_val > 0.5 then
                Cin_tb <= '1';
            else
                Cin_tb <= '0';
            end if;
            
            wait for SIM_TIME;
            
            -- Check against golden model
            if (S_tb /= expected_sum(NBIT_TEST-1 downto 0)) or (Cout_tb /= expected_sum(NBIT_TEST)) then
                report "[WARNING] Validation failed on random vector index " & integer'image(i) severity error;
                errors := errors + 1;
            end if;
            
            tests_run := tests_run + 1;
        end loop;

        -- Results
        if errors = 0 then
            report "[TB] PASSED: verified successfully." severity note;
        else
            report "[TB] FAILED: " & integer'image(errors) & " mismatches." severity error;
        end if;

		-- Force simulation to stop
        assert false report "[TB] Simulation finished." severity failure;
    end process;

end TEST;
