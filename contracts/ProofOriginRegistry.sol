// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ProofOriginRegistry {
    event ProofRecorded(bytes32 indexed hash, address indexed sender, uint256 timestamp);

    function recordProof(bytes32 hash) public {
        emit ProofRecorded(hash, msg.sender, block.timestamp);
    }
}

